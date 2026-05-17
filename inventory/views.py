from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Sum, Count, F, Q, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView,
)

from .models import (
    ConsumableItem, Supplier, StockBatch,
    StockMovement, PurchaseOrder, PurchaseOrderLine,
)
from .forms import (
    ConsumableItemForm, ConsumableItemFilterForm,
    SupplierForm,
    StockBatchForm,
    StockDispenseForm, StockAdjustmentForm, StockMovementFilterForm,
    PurchaseOrderForm, PurchaseOrderLineFormSet,
    POReceiveForm, PurchaseOrderFilterForm,
)


# ─────────────────────────────────────────────────────────────────────────────
# Permission mixins
# ─────────────────────────────────────────────────────────────────────────────

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Admin / superuser only."""
    def test_func(self):
        return getattr(self.request.user, 'is_admin', False)


class StoreKeeperMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Admin or any staff whose role is 'finance' (store keeper proxy).
    Adjust test_func if you add a dedicated storekeeper role later.
    """
    def test_func(self):
        u = self.request.user
        return u.is_superuser or getattr(u, 'is_admin', False) or getattr(u, 'is_finance', False)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard / Statistics
# ─────────────────────────────────────────────────────────────────────────────

class InventoryDashboardView(LoginRequiredMixin, TemplateView):
    """
    GET /inventory/
    High-level IMS statistics: stock value, low-stock items, recent movements,
    expiring batches, PO status summary.
    """
    template_name = 'inventory/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        soon = today + timezone.timedelta(days=90)

        # ── Item counts ────────────────────────────────────────────────────
        all_items = ConsumableItem.objects.filter(is_active=True)
        ctx['total_items'] = all_items.count()

        # Build quantity_on_hand per item via aggregation for efficiency
        # (avoids N+1 from calling .quantity_on_hand property per item)
        qty_map = dict(
            StockMovement.objects
            .values('item_id')
            .annotate(total=Sum('quantity_delta'))
            .values_list('item_id', 'total')
        )

        low_stock_items = [
            item for item in all_items
            if qty_map.get(item.pk, 0) <= item.reorder_level
        ]
        out_of_stock_items = [
            item for item in all_items
            if qty_map.get(item.pk, 0) <= 0
        ]
        ctx['low_stock_count']     = len(low_stock_items)
        ctx['out_of_stock_count']  = len(out_of_stock_items)
        ctx['low_stock_items']     = low_stock_items[:10]
        ctx['out_of_stock_items']  = out_of_stock_items[:10]

        # ── Stock value (sum of unit_cost × quantity_on_hand per item) ────
        # Approximation: uses item.unit_cost (not batch-weighted average)
        total_value = sum(
            item.unit_cost * max(qty_map.get(item.pk, 0), 0)
            for item in all_items
        )
        ctx['total_stock_value'] = total_value

        # ── Expiring batches ───────────────────────────────────────────────
        ctx['expiring_soon_batches'] = (
            StockBatch.objects
            .filter(expiry_date__gte=today, expiry_date__lte=soon)
            .select_related('item', 'supplier')
            .order_by('expiry_date')[:10]
        )
        ctx['expired_batches_count'] = StockBatch.objects.filter(
            expiry_date__lt=today
        ).count()

        # ── Recent movements ───────────────────────────────────────────────
        ctx['recent_movements'] = (
            StockMovement.objects
            .select_related('item', 'performed_by')
            .order_by('-created_at')[:15]
        )

        # ── PO summary ─────────────────────────────────────────────────────
        ctx['pending_pos'] = PurchaseOrder.objects.filter(
            status__in=[PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SUBMITTED]
        ).count()

        # ── Category breakdown ─────────────────────────────────────────────
        ctx['category_counts'] = (
            ConsumableItem.objects
            .filter(is_active=True)
            .values('category')
            .annotate(count=Count('id'))
            .order_by('category')
        )

        ctx['today'] = today
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
# ConsumableItem
# ─────────────────────────────────────────────────────────────────────────────

class ConsumableItemListView(LoginRequiredMixin, ListView):
    """GET /inventory/items/?q=&category=&department=&low_stock="""
    template_name = 'inventory/item_list.html'
    context_object_name = 'items'
    paginate_by = 30

    def get_queryset(self):
        qs = ConsumableItem.objects.filter(is_active=True)
        form = ConsumableItemFilterForm(self.request.GET)
        if form.is_valid():
            q    = form.cleaned_data.get('q')
            cat  = form.cleaned_data.get('category')
            dept = form.cleaned_data.get('department')
            if q:
                qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
            if cat:
                qs = qs.filter(category=cat)
            if dept:
                qs = qs.filter(department__icontains=dept)
        return qs.order_by('category', 'name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = ConsumableItemFilterForm(self.request.GET)
        ctx['is_admin'] = getattr(self.request.user, 'is_admin', False)

        # Annotate each item with its live quantity for the template
        # Build map once to avoid N+1
        qty_map = dict(
            StockMovement.objects
            .values('item_id')
            .annotate(total=Sum('quantity_delta'))
            .values_list('item_id', 'total')
        )
        # Attach to items as a non-model attribute
        for item in ctx['items']:
            item.qty_on_hand = qty_map.get(item.pk, 0)

        # Low stock filter (post-queryset because it's computed)
        low_stock_only = self.request.GET.get('low_stock')
        if low_stock_only:
            ctx['items'] = [i for i in ctx['items'] if i.qty_on_hand <= i.reorder_level]

        return ctx


class ConsumableItemDetailView(LoginRequiredMixin, DetailView):
    """GET /inventory/items/<pk>/"""
    model = ConsumableItem
    template_name = 'inventory/item_detail.html'
    context_object_name = 'item'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        item = self.object
        ctx['quantity_on_hand'] = item.quantity_on_hand
        ctx['is_low_stock']     = item.is_low_stock
        ctx['is_out_of_stock']  = item.is_out_of_stock
        ctx['batches'] = item.batches.select_related('supplier').order_by('expiry_date')
        ctx['recent_movements'] = (
            item.movements
            .select_related('performed_by', 'batch')
            .order_by('-created_at')[:20]
        )
        ctx['dispense_form']    = StockDispenseForm(initial={'item': item})
        ctx['adjustment_form']  = StockAdjustmentForm(initial={'item': item})
        return ctx


class ConsumableItemCreateView(StoreKeeperMixin, CreateView):
    """GET/POST /inventory/items/new/"""
    model = ConsumableItem
    form_class = ConsumableItemForm
    template_name = 'inventory/item_form.html'

    def get_success_url(self):
        return reverse('inventory:item-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Add Consumable Item'
        return ctx

    def form_valid(self, form):
        item = form.save(commit=False)
        item.created_by = self.request.user
        item.save()
        self.object = item
        messages.success(self.request, f"Item '{item.name}' ({item.sku}) added to inventory.")
        return redirect(self.get_success_url())


class ConsumableItemUpdateView(StoreKeeperMixin, UpdateView):
    """GET/POST /inventory/items/<pk>/edit/"""
    model = ConsumableItem
    form_class = ConsumableItemForm
    template_name = 'inventory/item_form.html'

    def get_success_url(self):
        return reverse('inventory:item-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = f'Edit — {self.object.name}'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Item '{self.object.name}' updated.")
        return super().form_valid(form)


class ConsumableItemDeactivateView(StoreKeeperMixin, View):
    """POST /inventory/items/<pk>/deactivate/ — soft delete."""
    def post(self, request, pk):
        item = get_object_or_404(ConsumableItem, pk=pk)
        item.is_active = False
        item.save(update_fields=['is_active'])
        messages.success(request, f"'{item.name}' deactivated.")
        return redirect(reverse('inventory:item-list'))


# ─────────────────────────────────────────────────────────────────────────────
# Supplier
# ─────────────────────────────────────────────────────────────────────────────

class SupplierListView(LoginRequiredMixin, ListView):
    """GET /inventory/suppliers/"""
    model = Supplier
    template_name = 'inventory/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 25

    def get_queryset(self):
        qs = Supplier.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(contact_name__icontains=q) | Q(phone__icontains=q))
        return qs.order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class SupplierDetailView(LoginRequiredMixin, DetailView):
    """GET /inventory/suppliers/<pk>/"""
    model = Supplier
    template_name = 'inventory/supplier_detail.html'
    context_object_name = 'supplier'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['purchase_orders'] = (
            self.object.purchase_orders
            .order_by('-created_at')[:10]
        )
        ctx['batches'] = (
            self.object.batches
            .select_related('item')
            .order_by('-received_date')[:10]
        )
        return ctx


class SupplierCreateView(StoreKeeperMixin, CreateView):
    """GET/POST /inventory/suppliers/new/"""
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/supplier_form.html'
    success_url = reverse_lazy('inventory:supplier-list')

    def form_valid(self, form):
        messages.success(self.request, f"Supplier '{form.instance.name}' added.")
        return super().form_valid(form)


class SupplierUpdateView(StoreKeeperMixin, UpdateView):
    """GET/POST /inventory/suppliers/<pk>/edit/"""
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/supplier_form.html'
    success_url = reverse_lazy('inventory:supplier-list')

    def form_valid(self, form):
        messages.success(self.request, f"Supplier '{self.object.name}' updated.")
        return super().form_valid(form)


# ─────────────────────────────────────────────────────────────────────────────
# Stock Batch
# ─────────────────────────────────────────────────────────────────────────────

class StockBatchListView(LoginRequiredMixin, ListView):
    """GET /inventory/batches/?item=&expiring="""
    template_name = 'inventory/batch_list.html'
    context_object_name = 'batches'
    paginate_by = 30

    def get_queryset(self):
        qs = StockBatch.objects.select_related('item', 'supplier', 'received_by')
        item_id = self.request.GET.get('item')
        expiring = self.request.GET.get('expiring')
        if item_id:
            qs = qs.filter(item_id=item_id)
        if expiring:
            soon = timezone.localdate() + timezone.timedelta(days=90)
            qs = qs.filter(expiry_date__lte=soon, expiry_date__gte=timezone.localdate())
        return qs.order_by('expiry_date', 'item__name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['today'] = timezone.localdate()
        ctx['filters'] = self.request.GET
        return ctx


class StockBatchCreateView(StoreKeeperMixin, CreateView):
    """GET/POST /inventory/batches/new/ — manual batch registration."""
    model = StockBatch
    form_class = StockBatchForm
    template_name = 'inventory/batch_form.html'

    def get_success_url(self):
        return reverse('inventory:item-detail', kwargs={'pk': self.object.item.pk})

    def get_initial(self):
        initial = super().get_initial()
        item_id = self.request.GET.get('item')
        if item_id:
            initial['item'] = item_id
        return initial

    @transaction.atomic
    def form_valid(self, form):
        batch = form.save(commit=False)
        batch.received_by = self.request.user
        batch.save()
        self.object = batch

        # Auto-create a StockMovement (receive) for this batch
        StockMovement.objects.create(
            item=batch.item,
            batch=batch,
            movement_type=StockMovement.TYPE_RECEIVE,
            quantity_delta=batch.quantity_received,
            reference=f"BATCH-{batch.pk}",
            notes=f"Manual batch registration — {batch.batch_number or 'no batch number'}",
            performed_by=self.request.user,
        )

        messages.success(
            self.request,
            f"{batch.quantity_received} {batch.item.unit} of '{batch.item.name}' received into stock."
        )
        return redirect(self.get_success_url())


# ─────────────────────────────────────────────────────────────────────────────
# Stock Movement  (ledger / history)
# ─────────────────────────────────────────────────────────────────────────────

class StockMovementListView(LoginRequiredMixin, ListView):
    """GET /inventory/movements/?item=&movement_type=&date_from=&date_to=&department="""
    template_name = 'inventory/movement_list.html'
    context_object_name = 'movements'
    paginate_by = 40

    def get_queryset(self):
        qs = StockMovement.objects.select_related(
            'item', 'batch', 'performed_by', 'visit__patient'
        )
        form = StockMovementFilterForm(self.request.GET)
        if form.is_valid():
            d = form.cleaned_data
            if d.get('item'):
                qs = qs.filter(item=d['item'])
            if d.get('movement_type'):
                qs = qs.filter(movement_type=d['movement_type'])
            if d.get('date_from'):
                qs = qs.filter(created_at__date__gte=d['date_from'])
            if d.get('date_to'):
                qs = qs.filter(created_at__date__lte=d['date_to'])
            if d.get('department'):
                qs = qs.filter(department__icontains=d['department'])
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = StockMovementFilterForm(self.request.GET)
        return ctx


class StockMovementDetailView(LoginRequiredMixin, DetailView):
    """GET /inventory/movements/<pk>/"""
    model = StockMovement
    template_name = 'inventory/movement_detail.html'
    context_object_name = 'movement'

    def get_queryset(self):
        return StockMovement.objects.select_related(
            'item', 'batch', 'performed_by', 'visit__patient'
        )


# ─────────────────────────────────────────────────────────────────────────────
# Dispense View  (POST /inventory/dispense/)
# ─────────────────────────────────────────────────────────────────────────────

class StockDispenseView(StoreKeeperMixin, View):
    """
    GET  — render dispense form
    POST — validate, resolve batch (FEFO if not specified), create StockMovement
    """
    template_name = 'inventory/dispense_form.html'

    def get(self, request):
        form = StockDispenseForm()
        return render(request, self.template_name, {'form': form, 'title': 'Dispense Stock'})

    @transaction.atomic
    def post(self, request):
        form = StockDispenseForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'title': 'Dispense Stock'})

        d = form.cleaned_data
        item  = d['item']
        qty   = d['quantity']
        batch = d.get('batch')

        # FEFO: pick the oldest non-expired batch if none specified
        if not batch:
            batch = (
                item.batches
                .filter(
                    Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.localdate())
                )
                .order_by('expiry_date')
                .first()
            )

        # Determine visit FK if reference looks like a visit ID
        visit = None
        ref = d.get('reference', '')
        if ref and ref.isdigit():
            from patients.models import Visit
            visit = Visit.objects.filter(pk=ref).first()

        StockMovement.objects.create(
            item=item,
            batch=batch,
            movement_type=StockMovement.TYPE_DISPENSE,
            quantity_delta=-qty,           # negative = stock out
            reference=ref,
            department=d.get('department', ''),
            visit=visit,
            notes=d.get('notes', ''),
            performed_by=request.user,
        )

        messages.success(
            request,
            f"Dispensed {qty} {item.unit} of '{item.name}'. "
            f"New stock: {item.quantity_on_hand} {item.unit}."
        )

        # Alert if stock now at or below reorder level
        if item.is_low_stock:
            messages.warning(
                request,
                f"⚠ '{item.name}' is now at or below its reorder level "
                f"({item.reorder_level} {item.unit})."
            )

        return redirect(reverse('inventory:item-detail', kwargs={'pk': item.pk}))


# ─────────────────────────────────────────────────────────────────────────────
# Adjustment / Write-off / Return / Transfer
# ─────────────────────────────────────────────────────────────────────────────

class StockAdjustmentView(StoreKeeperMixin, View):
    """
    GET  — render adjustment form
    POST — create a StockMovement of the chosen type
    """
    template_name = 'inventory/adjustment_form.html'

    def get(self, request):
        item_id = request.GET.get('item')
        initial = {'item': item_id} if item_id else {}
        form = StockAdjustmentForm(initial=initial)
        return render(request, self.template_name, {'form': form, 'title': 'Stock Adjustment'})

    @transaction.atomic
    def post(self, request):
        form = StockAdjustmentForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'title': 'Stock Adjustment'})

        d = form.cleaned_data
        item          = d['item']
        movement_type = d['movement_type']
        qty           = d['quantity']

        # Convert to signed delta based on type
        if movement_type in StockMovement.NEGATIVE_TYPES:
            delta = -qty
        else:
            delta = qty

        StockMovement.objects.create(
            item=item,
            batch=d.get('batch'),
            movement_type=movement_type,
            quantity_delta=delta,
            reference=d.get('reference', ''),
            department=d.get('department', ''),
            notes=d.get('notes', ''),
            performed_by=request.user,
        )

        label = dict(StockMovement.TYPE_CHOICES).get(movement_type, movement_type)
        messages.success(
            request,
            f"{label}: {qty} {item.unit} of '{item.name}'. "
            f"New stock: {item.quantity_on_hand} {item.unit}."
        )
        return redirect(reverse('inventory:item-detail', kwargs={'pk': item.pk}))


# ─────────────────────────────────────────────────────────────────────────────
# Purchase Orders
# ─────────────────────────────────────────────────────────────────────────────

class PurchaseOrderListView(LoginRequiredMixin, ListView):
    """GET /inventory/purchase-orders/"""
    template_name = 'inventory/po_list.html'
    context_object_name = 'orders'
    paginate_by = 25

    def get_queryset(self):
        qs = PurchaseOrder.objects.select_related('supplier', 'raised_by')
        form = PurchaseOrderFilterForm(self.request.GET)
        if form.is_valid():
            d = form.cleaned_data
            if d.get('status'):
                qs = qs.filter(status=d['status'])
            if d.get('supplier'):
                qs = qs.filter(supplier=d['supplier'])
            if d.get('date_from'):
                qs = qs.filter(ordered_date__gte=d['date_from'])
            if d.get('date_to'):
                qs = qs.filter(ordered_date__lte=d['date_to'])
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = PurchaseOrderFilterForm(self.request.GET)
        return ctx


class PurchaseOrderDetailView(LoginRequiredMixin, DetailView):
    """GET /inventory/purchase-orders/<pk>/"""
    model = PurchaseOrder
    template_name = 'inventory/po_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        return PurchaseOrder.objects.select_related('supplier', 'raised_by', 'received_by')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['lines'] = self.object.lines.select_related('item')
        ctx['receive_form'] = POReceiveForm()
        ctx['can_receive'] = self.object.status == PurchaseOrder.STATUS_SUBMITTED
        ctx['can_submit']  = self.object.status == PurchaseOrder.STATUS_DRAFT
        ctx['can_cancel']  = self.object.status in (
            PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SUBMITTED
        )
        return ctx


class PurchaseOrderCreateView(StoreKeeperMixin, CreateView):
    """GET/POST /inventory/purchase-orders/new/"""
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'inventory/po_form.html'

    def get_success_url(self):
        return reverse('inventory:po-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['line_formset'] = PurchaseOrderLineFormSet(self.request.POST)
        else:
            ctx['line_formset'] = PurchaseOrderLineFormSet()
        ctx['form_title'] = 'New Purchase Order'
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        ctx = self.get_context_data()
        line_formset = ctx['line_formset']

        if not line_formset.is_valid():
            return self.render_to_response(ctx)

        order = form.save(commit=False)
        order.raised_by = self.request.user
        order.save()
        self.object = order

        line_formset.instance = order
        line_formset.save()

        messages.success(self.request, f"Purchase Order {order.po_number} created.")
        return redirect(self.get_success_url())


class PurchaseOrderUpdateView(StoreKeeperMixin, UpdateView):
    """GET/POST /inventory/purchase-orders/<pk>/edit/ — only DRAFT orders."""
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'inventory/po_form.html'

    def get_success_url(self):
        return reverse('inventory:po-detail', kwargs={'pk': self.object.pk})

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.status != PurchaseOrder.STATUS_DRAFT:
            messages.error(self.request, "Only draft purchase orders can be edited.")
            redirect(self.get_success_url())
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['line_formset'] = PurchaseOrderLineFormSet(self.request.POST, instance=self.object)
        else:
            ctx['line_formset'] = PurchaseOrderLineFormSet(instance=self.object)
        ctx['form_title'] = f'Edit PO — {self.object.po_number}'
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        ctx = self.get_context_data()
        line_formset = ctx['line_formset']
        if not line_formset.is_valid():
            return self.render_to_response(ctx)
        form.save()
        line_formset.save()
        messages.success(self.request, f"{self.object.po_number} updated.")
        return redirect(self.get_success_url())


class PurchaseOrderSubmitView(StoreKeeperMixin, View):
    """POST /inventory/purchase-orders/<pk>/submit/ — DRAFT → SUBMITTED."""
    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        if order.status != PurchaseOrder.STATUS_DRAFT:
            messages.error(request, "Only draft orders can be submitted.")
            return redirect(reverse('inventory:po-detail', kwargs={'pk': pk}))
        order.status = PurchaseOrder.STATUS_SUBMITTED
        order.save(update_fields=['status', 'updated_at'])
        messages.success(request, f"{order.po_number} submitted to supplier.")
        return redirect(reverse('inventory:po-detail', kwargs={'pk': pk}))


class PurchaseOrderReceiveView(StoreKeeperMixin, View):
    """
    POST /inventory/purchase-orders/<pk>/receive/
    Marks the PO as RECEIVED, creates StockBatch + StockMovement for each line.
    """
    @transaction.atomic
    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)

        if order.status != PurchaseOrder.STATUS_SUBMITTED:
            messages.error(request, "Only submitted orders can be marked as received.")
            return redirect(reverse('inventory:po-detail', kwargs={'pk': pk}))

        form = POReceiveForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please provide a valid received date.")
            return redirect(reverse('inventory:po-detail', kwargs={'pk': pk}))

        received_date = form.cleaned_data['received_date']
        extra_notes   = form.cleaned_data.get('notes', '')

        for line in order.lines.select_related('item'):
            # Create a batch for this PO line
            batch = StockBatch.objects.create(
                item=line.item,
                supplier=order.supplier,
                batch_number=line.batch_number,
                quantity_received=line.quantity_ordered,
                unit_cost=line.unit_cost,
                received_date=received_date,
                expiry_date=line.expiry_date,
                notes=f"Auto-created from {order.po_number}. {extra_notes}".strip(),
                received_by=request.user,
            )
            # Record receipt in the movement ledger
            StockMovement.objects.create(
                item=line.item,
                batch=batch,
                movement_type=StockMovement.TYPE_RECEIVE,
                quantity_delta=line.quantity_ordered,
                reference=order.po_number,
                notes=f"Received via {order.po_number}",
                performed_by=request.user,
            )
            # Mark how many were received on the line
            line.quantity_received = line.quantity_ordered
            line.save(update_fields=['quantity_received'])

        # Update PO header
        order.status        = PurchaseOrder.STATUS_RECEIVED
        order.received_date = received_date
        order.received_by   = request.user
        order.save(update_fields=['status', 'received_date', 'received_by', 'updated_at'])

        messages.success(request, f"{order.po_number} marked as received. Stock updated.")
        return redirect(reverse('inventory:po-detail', kwargs={'pk': pk}))


class PurchaseOrderCancelView(StoreKeeperMixin, View):
    """POST /inventory/purchase-orders/<pk>/cancel/"""
    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        if order.status not in (PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SUBMITTED):
            messages.error(request, "Only draft or submitted orders can be cancelled.")
            return redirect(reverse('inventory:po-detail', kwargs={'pk': pk}))
        order.status = PurchaseOrder.STATUS_CANCELLED
        order.save(update_fields=['status', 'updated_at'])
        messages.success(request, f"{order.po_number} cancelled.")
        return redirect(reverse('inventory:po-list'))


# ─────────────────────────────────────────────────────────────────────────────
# Statistics / Reports
# ─────────────────────────────────────────────────────────────────────────────

class InventoryStatsView(LoginRequiredMixin, TemplateView):
    """
    GET /inventory/stats/
    Detailed statistical breakdown:
        - consumption by item (last 30 days)
        - top-dispensed items
        - stock value by category
        - monthly receive vs dispense totals
    """
    template_name = 'inventory/stats.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today    = timezone.localdate()
        day_30   = today - timezone.timedelta(days=30)
        day_7    = today - timezone.timedelta(days=7)

        # ── Top dispensed items (last 30 days) ────────────────────────────
        ctx['top_dispensed'] = (
            StockMovement.objects
            .filter(
                movement_type=StockMovement.TYPE_DISPENSE,
                created_at__date__gte=day_30,
            )
            .values('item__name', 'item__unit', 'item__sku')
            .annotate(total_dispensed=Sum('quantity_delta'))   # will be negative
            .order_by('total_dispensed')[:10]                  # most negative = most consumed
        )

        # ── Stock received in last 30 days ─────────────────────────────────
        ctx['total_received_30d'] = (
            StockMovement.objects
            .filter(
                movement_type=StockMovement.TYPE_RECEIVE,
                created_at__date__gte=day_30,
            )
            .aggregate(total=Sum('quantity_delta'))['total'] or 0
        )

        # ── Write-offs (last 30 days) ──────────────────────────────────────
        ctx['writeoffs_30d'] = (
            StockMovement.objects
            .filter(
                movement_type=StockMovement.TYPE_WRITEOFF,
                created_at__date__gte=day_30,
            )
            .aggregate(total=Sum('quantity_delta'))['total'] or 0
        )

        # ── Stock value by category ────────────────────────────────────────
        # Aggregate: for each active item, value = unit_cost × quantity_on_hand
        items = ConsumableItem.objects.filter(is_active=True).select_related()
        qty_map = dict(
            StockMovement.objects
            .values('item_id')
            .annotate(total=Sum('quantity_delta'))
            .values_list('item_id', 'total')
        )
        category_value = {}
        for item in items:
            qty = max(qty_map.get(item.pk, 0), 0)
            cat = item.get_category_display()
            category_value[cat] = category_value.get(cat, 0) + float(item.unit_cost * qty)
        ctx['category_value'] = sorted(category_value.items(), key=lambda x: -x[1])

        # ── Daily movement summary (last 7 days) ───────────────────────────
        trend = []
        for i in range(6, -1, -1):
            d = today - timezone.timedelta(days=i)
            received = (
                StockMovement.objects
                .filter(created_at__date=d, movement_type=StockMovement.TYPE_RECEIVE)
                .aggregate(t=Sum('quantity_delta'))['t'] or 0
            )
            dispensed = abs(
                StockMovement.objects
                .filter(created_at__date=d, movement_type=StockMovement.TYPE_DISPENSE)
                .aggregate(t=Sum('quantity_delta'))['t'] or 0
            )
            trend.append({
                'date': d.strftime('%d %b'),
                'received': received,
                'dispensed': dispensed,
            })
        ctx['weekly_trend'] = trend

        # ── Low stock summary ──────────────────────────────────────────────
        all_items = list(ConsumableItem.objects.filter(is_active=True))
        ctx['low_stock_items'] = [
            {'item': item, 'qty': qty_map.get(item.pk, 0)}
            for item in all_items
            if qty_map.get(item.pk, 0) <= item.reorder_level
        ]

        # ── PO stats ───────────────────────────────────────────────────────
        ctx['po_stats'] = (
            PurchaseOrder.objects
            .values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )

        ctx['today'] = today
        return ctx


class LowStockAlertView(LoginRequiredMixin, TemplateView):
    """GET /inventory/alerts/ — focused low-stock and expiry alert page."""
    template_name = 'inventory/alerts.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        soon  = today + timezone.timedelta(days=90)

        qty_map = dict(
            StockMovement.objects
            .values('item_id')
            .annotate(total=Sum('quantity_delta'))
            .values_list('item_id', 'total')
        )

        all_items = ConsumableItem.objects.filter(is_active=True)

        ctx['out_of_stock'] = [
            {'item': i, 'qty': qty_map.get(i.pk, 0)}
            for i in all_items if qty_map.get(i.pk, 0) <= 0
        ]
        ctx['low_stock'] = [
            {'item': i, 'qty': qty_map.get(i.pk, 0)}
            for i in all_items
            if 0 < qty_map.get(i.pk, 0) <= i.reorder_level
        ]
        ctx['expiring_soon'] = (
            StockBatch.objects
            .filter(expiry_date__gte=today, expiry_date__lte=soon)
            .select_related('item', 'supplier')
            .order_by('expiry_date')
        )
        ctx['expired'] = (
            StockBatch.objects
            .filter(expiry_date__lt=today)
            .select_related('item', 'supplier')
            .order_by('expiry_date')
        )
        ctx['today'] = today
        return ctx