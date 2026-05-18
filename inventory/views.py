from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Sum, Count, F, Q, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
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
    BulkUsageHeaderForm, UsageLineFormSet,
)


# ─────────────────────────────────────────────────────────────────────────────
# Permission mixins
# ─────────────────────────────────────────────────────────────────────────────

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Admin / superuser only."""
    def test_func(self):
        return getattr(self.request.user, 'is_admin', False)


class StoreKeeperMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Admin or any staff whose role is 'finance' (store keeper proxy)."""
    def test_func(self):
        u = self.request.user
        return u.is_superuser or getattr(u, 'is_admin', False) or getattr(u, 'is_finance', False)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard / Statistics
# ─────────────────────────────────────────────────────────────────────────────

class InventoryDashboardView(LoginRequiredMixin, TemplateView):
    """GET /inventory/ — High-level IMS statistics."""
    template_name = 'inventory/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        soon = today + timezone.timedelta(days=90)

        all_items = ConsumableItem.objects.filter(is_active=True)
        ctx['total_items'] = all_items.count()

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

        total_value = sum(
            item.unit_cost * max(qty_map.get(item.pk, 0), 0)
            for item in all_items
        )
        ctx['total_stock_value'] = total_value

        ctx['expiring_soon_batches'] = (
            StockBatch.objects
            .filter(expiry_date__gte=today, expiry_date__lte=soon)
            .select_related('item', 'supplier')
            .order_by('expiry_date')[:10]
        )
        ctx['expired_batches_count'] = StockBatch.objects.filter(
            expiry_date__lt=today
        ).count()

        ctx['recent_movements'] = (
            StockMovement.objects
            .select_related('item', 'performed_by')
            .order_by('-created_at')[:15]
        )

        ctx['pending_pos'] = PurchaseOrder.objects.filter(
            status__in=[PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SUBMITTED]
        ).count()

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

        qty_map = dict(
            StockMovement.objects
            .values('item_id')
            .annotate(total=Sum('quantity_delta'))
            .values_list('item_id', 'total')
        )
        for item in ctx['items']:
            item.qty_on_hand = qty_map.get(item.pk, 0)

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
        ctx['is_admin'] = getattr(self.request.user, 'is_admin', False)
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
    model = Supplier
    template_name = 'inventory/supplier_detail.html'
    context_object_name = 'supplier'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['purchase_orders'] = self.object.purchase_orders.order_by('-created_at')[:10]
        ctx['batches'] = self.object.batches.select_related('item').order_by('-received_date')[:10]
        return ctx


class SupplierCreateView(StoreKeeperMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/supplier_form.html'
    success_url = reverse_lazy('inventory:supplier-list')

    def form_valid(self, form):
        messages.success(self.request, f"Supplier '{form.instance.name}' added.")
        return super().form_valid(form)


class SupplierUpdateView(StoreKeeperMixin, UpdateView):
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
    model = StockMovement
    template_name = 'inventory/movement_detail.html'
    context_object_name = 'movement'

    def get_queryset(self):
        return StockMovement.objects.select_related(
            'item', 'batch', 'performed_by', 'visit__patient'
        )


# ─────────────────────────────────────────────────────────────────────────────
# Dispense View  (storekeeper single-item dispense)
# ─────────────────────────────────────────────────────────────────────────────

class StockDispenseView(StoreKeeperMixin, View):
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

        if not batch:
            batch = (
                item.batches
                .filter(
                    Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.localdate())
                )
                .order_by('expiry_date')
                .first()
            )

        visit = None
        ref = d.get('reference', '')
        if ref and ref.isdigit():
            try:
                from patients.models import Visit
                visit = Visit.objects.filter(pk=ref).first()
            except Exception:
                pass

        StockMovement.objects.create(
            item=item,
            batch=batch,
            movement_type=StockMovement.TYPE_DISPENSE,
            quantity_delta=-qty,
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

        delta = -qty if movement_type in StockMovement.NEGATIVE_TYPES else qty

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
# Bulk Usage Recording  (doctor/nurse — multi-item usage in one submission)
# ─────────────────────────────────────────────────────────────────────────────

class BulkUsageView(LoginRequiredMixin, View):
    """
    GET  /inventory/record-usage/
         Shows the multi-item usage form. Every active item is loaded and
         annotated with its current stock level.

         Out-of-stock items are passed to the template so they can be shown
         greyed-out and disabled in the <select>. This means clinical staff
         can still see the item exists, know it's unavailable, and flag it
         to the storekeeper — they just can't accidentally select it.

    POST /inventory/record-usage/
         Validates all lines atomically:
           • Duplicate items in same submission → rejected
           • Any item with insufficient stock    → whole submission rejected
           • No partial deductions ever happen

         On success, creates one StockMovement (TYPE_DISPENSE) per line and
         emits low-stock warnings for any item that falls to or below its
         reorder level after the deduction.
    """
    template_name = 'inventory/usage_form.html'

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_item_stock_map(self):
        """Return {item_pk: quantity_on_hand} for all active items."""
        return dict(
            StockMovement.objects
            .values('item_id')
            .annotate(total=Sum('quantity_delta'))
            .values_list('item_id', 'total')
        )

    def _all_items_with_stock(self):
        """
        Return all active ConsumableItem objects annotated with:
            qty_on_hand  — current stock level (may be 0 or negative)
            is_out       — True if qty_on_hand <= 0
            is_low       — True if 0 < qty_on_hand <= reorder_level

        Ordered by category then name so the dropdown groups naturally.
        """
        qty_map = self._build_item_stock_map()
        items = list(
            ConsumableItem.objects.filter(is_active=True).order_by('category', 'name')
        )
        for item in items:
            qty = qty_map.get(item.pk, 0)
            item.qty_on_hand = qty
            item.is_out  = qty <= 0
            item.is_low  = 0 < qty <= item.reorder_level
        return items

    # ── GET ───────────────────────────────────────────────────────────────────

    def get(self, request):
        header_form = BulkUsageHeaderForm()
        formset     = UsageLineFormSet(prefix='lines')
        items       = self._all_items_with_stock()

        # Pre-fill department from user profile if available
        dept = getattr(request.user, 'department', '') or ''
        if dept:
            header_form.initial['department'] = dept

        return render(request, self.template_name, {
            'header_form': header_form,
            'formset':     formset,
            'items':       items,
        })

    # ── POST ──────────────────────────────────────────────────────────────────

    @transaction.atomic
    def post(self, request):
        header_form = BulkUsageHeaderForm(request.POST)
        formset     = UsageLineFormSet(request.POST, prefix='lines')
        items       = self._all_items_with_stock()

        header_ok  = header_form.is_valid()
        formset_ok = formset.is_valid()

        if not (header_ok and formset_ok):
            return render(request, self.template_name, {
                'header_form': header_form,
                'formset':     formset,
                'items':       items,
            })

        # ── Gather valid (non-deleted) lines ──────────────────────────────
        lines = [
            f.cleaned_data for f in formset
            if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
        ]

        if not lines:
            messages.error(request, "Please add at least one item to record usage.")
            return render(request, self.template_name, {
                'header_form': header_form,
                'formset':     formset,
                'items':       items,
            })

        hd          = header_form.cleaned_data
        context_lbl = dict(BulkUsageHeaderForm.CONTEXT_CHOICES).get(
            hd['context_type'], hd['context_type']
        )
        department  = hd.get('department', '')
        reference   = hd.get('reference', '')
        notes       = hd.get('notes', '')

        # ── Pre-validate ALL lines before touching the DB ─────────────────
        # This ensures the whole batch is accepted or rejected together.
        qty_map = self._build_item_stock_map()
        errors  = []
        seen_items = {}  # detect duplicates in same submission

        for idx, line in enumerate(lines, 1):
            item = line['item']
            qty  = line['quantity']
            on_hand = qty_map.get(item.pk, 0)

            if item.pk in seen_items:
                errors.append(
                    f"Line {idx}: '{item.name}' appears more than once. "
                    f"Combine the quantities into a single line."
                )
                continue

            seen_items[item.pk] = qty

            if on_hand <= 0:
                errors.append(
                    f"Line {idx}: '{item.name}' is out of stock "
                    f"(0 {item.unit} available). Please notify the storekeeper."
                )
            elif on_hand < qty:
                errors.append(
                    f"Line {idx}: Insufficient stock for '{item.name}'. "
                    f"Requested {qty} {item.unit}, on hand: {on_hand} {item.unit}."
                )

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, self.template_name, {
                'header_form': header_form,
                'formset':     formset,
                'items':       items,
            })

        # ── Resolve optional visit FK ─────────────────────────────────────
        visit = None
        if reference and reference.isdigit():
            try:
                from patients.models import Visit
                visit = Visit.objects.filter(pk=reference).first()
            except Exception:
                pass

        # ── Create movements atomically ───────────────────────────────────
        created_movements  = []
        low_stock_warnings = []

        for line in lines:
            item = line['item']
            qty  = line['quantity']

            # FEFO batch selection — oldest non-expired batch goes first
            batch = (
                item.batches
                .filter(
                    Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.localdate())
                )
                .order_by('expiry_date')
                .first()
            )

            movement = StockMovement.objects.create(
                item=item,
                batch=batch,
                movement_type=StockMovement.TYPE_DISPENSE,
                quantity_delta=-qty,
                reference=reference or f"USAGE-{context_lbl}",
                department=department,
                visit=visit,
                notes=(
                    f"Bulk usage — {context_lbl}"
                    + (f" | {notes}" if notes else "")
                ),
                performed_by=request.user,
            )
            created_movements.append(movement)

            # Check stock level after deduction for warnings
            new_qty = qty_map.get(item.pk, 0) - qty
            if new_qty <= 0:
                low_stock_warnings.append(
                    f"'{item.name}' is now OUT OF STOCK — notify the storekeeper immediately."
                )
            elif new_qty <= item.reorder_level:
                low_stock_warnings.append(
                    f"'{item.name}' is now LOW ({new_qty} {item.unit} remaining). "
                    f"Reorder level: {item.reorder_level} {item.unit}."
                )

        # ── Success messages ──────────────────────────────────────────────
        total_lines = len(created_movements)
        messages.success(
            request,
            f"✓ Usage recorded — {total_lines} item{'s' if total_lines != 1 else ''} "
            f"deducted from stock. "
            f"Context: {context_lbl}"
            + (f" | Ref: {reference}" if reference else "")
            + "."
        )
        for warn in low_stock_warnings:
            messages.warning(request, f"⚠ {warn}")

        return redirect(reverse('inventory:usage-history'))


# ─────────────────────────────────────────────────────────────────────────────
# Usage History  (filtered ledger of DISPENSE movements)
# ─────────────────────────────────────────────────────────────────────────────

class UsageHistoryView(LoginRequiredMixin, ListView):
    """
    GET /inventory/usage-history/
    Filtered ledger view showing only DISPENSE movements, readable as a
    clinical usage log.
    """
    template_name = 'inventory/usage_history.html'
    context_object_name = 'movements'
    paginate_by = 40

    def get_queryset(self):
        qs = StockMovement.objects.filter(
            movement_type=StockMovement.TYPE_DISPENSE
        ).select_related('item', 'batch', 'performed_by', 'visit')

        item_id = self.request.GET.get('item')
        dept    = self.request.GET.get('department', '').strip()
        ref     = self.request.GET.get('reference', '').strip()
        df      = self.request.GET.get('date_from')
        dt      = self.request.GET.get('date_to')
        by      = self.request.GET.get('performed_by', '').strip()

        if item_id:
            qs = qs.filter(item_id=item_id)
        if dept:
            qs = qs.filter(department__icontains=dept)
        if ref:
            qs = qs.filter(reference__icontains=ref)
        if df:
            qs = qs.filter(created_at__date__gte=df)
        if dt:
            qs = qs.filter(created_at__date__lte=dt)
        if by:
            qs = qs.filter(
                Q(performed_by__first_name__icontains=by) |
                Q(performed_by__last_name__icontains=by)
            )

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items']   = ConsumableItem.objects.filter(is_active=True).order_by('name')
        ctx['filters'] = self.request.GET
        ctx['today']   = timezone.localdate()
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
# API: Item stock info (used by usage form JS to show live stock levels)
# ─────────────────────────────────────────────────────────────────────────────

class ItemStockInfoView(LoginRequiredMixin, View):
    """
    GET /inventory/api/item-stock/?ids=1,2,3
    Returns JSON stock info for the given item PKs.
    Used by the bulk usage form JS to display live on-hand quantities.
    """
    def get(self, request):
        ids_raw = request.GET.get('ids', '')
        try:
            pks = [int(x) for x in ids_raw.split(',') if x.strip().isdigit()]
        except ValueError:
            pks = []

        if not pks:
            return JsonResponse({'items': []})

        qty_map = dict(
            StockMovement.objects
            .filter(item_id__in=pks)
            .values('item_id')
            .annotate(total=Sum('quantity_delta'))
            .values_list('item_id', 'total')
        )

        items = ConsumableItem.objects.filter(pk__in=pks, is_active=True)
        data = []
        for item in items:
            qty = qty_map.get(item.pk, 0)
            data.append({
                'id':            item.pk,
                'name':          item.name,
                'unit':          item.unit,
                'qty_on_hand':   qty,
                'reorder_level': item.reorder_level,
                'is_low':        qty <= item.reorder_level,
                'is_out':        qty <= 0,
            })

        return JsonResponse({'items': data})


# ─────────────────────────────────────────────────────────────────────────────
# Purchase Orders
# ─────────────────────────────────────────────────────────────────────────────

class PurchaseOrderListView(LoginRequiredMixin, ListView):
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
    model = PurchaseOrder
    template_name = 'inventory/po_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        return PurchaseOrder.objects.select_related('supplier', 'raised_by', 'received_by')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = self.object
        ctx['lines']        = order.lines.select_related('item')
        ctx['can_submit']   = order.status == PurchaseOrder.STATUS_DRAFT
        ctx['can_receive']  = order.status == PurchaseOrder.STATUS_SUBMITTED
        ctx['can_cancel']   = order.status in (PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SUBMITTED)
        ctx['receive_form'] = POReceiveForm()
        return ctx


class PurchaseOrderCreateView(StoreKeeperMixin, CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'inventory/po_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'New Purchase Order'
        if self.request.POST:
            ctx['line_formset'] = PurchaseOrderLineFormSet(self.request.POST, prefix='lines')
        else:
            ctx['line_formset'] = PurchaseOrderLineFormSet(prefix='lines')
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
        return redirect(reverse('inventory:po-detail', kwargs={'pk': order.pk}))


class PurchaseOrderUpdateView(StoreKeeperMixin, UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'inventory/po_form.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.status not in (PurchaseOrder.STATUS_DRAFT,):
            messages.error(self.request, "Only draft orders can be edited.")
            raise ValueError("Cannot edit non-draft PO")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = f'Edit {self.object.po_number}'
        if self.request.POST:
            ctx['line_formset'] = PurchaseOrderLineFormSet(
                self.request.POST, instance=self.object, prefix='lines'
            )
        else:
            ctx['line_formset'] = PurchaseOrderLineFormSet(instance=self.object, prefix='lines')
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
        return redirect(reverse('inventory:po-detail', kwargs={'pk': self.object.pk}))


class PurchaseOrderSubmitView(StoreKeeperMixin, View):
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
    @transaction.atomic
    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        if order.status != PurchaseOrder.STATUS_SUBMITTED:
            messages.error(request, "Only submitted orders can be marked received.")
            return redirect(reverse('inventory:po-detail', kwargs={'pk': pk}))

        receive_form = POReceiveForm(request.POST)
        if not receive_form.is_valid():
            messages.error(request, "Invalid received date.")
            return redirect(reverse('inventory:po-detail', kwargs={'pk': pk}))

        received_date = receive_form.cleaned_data['received_date']
        extra_notes   = receive_form.cleaned_data.get('notes', '')

        for line in order.lines.select_related('item'):
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
            StockMovement.objects.create(
                item=line.item,
                batch=batch,
                movement_type=StockMovement.TYPE_RECEIVE,
                quantity_delta=line.quantity_ordered,
                reference=order.po_number,
                notes=f"Received via {order.po_number}",
                performed_by=request.user,
            )
            line.quantity_received = line.quantity_ordered
            line.save(update_fields=['quantity_received'])

        order.status        = PurchaseOrder.STATUS_RECEIVED
        order.received_date = received_date
        order.received_by   = request.user
        order.save(update_fields=['status', 'received_date', 'received_by', 'updated_at'])

        messages.success(request, f"{order.po_number} marked as received. Stock updated.")
        return redirect(reverse('inventory:po-detail', kwargs={'pk': pk}))


class PurchaseOrderCancelView(StoreKeeperMixin, View):
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
    template_name = 'inventory/stats.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today  = timezone.localdate()
        day_30 = today - timezone.timedelta(days=30)

        ctx['top_dispensed'] = (
            StockMovement.objects
            .filter(movement_type=StockMovement.TYPE_DISPENSE, created_at__date__gte=day_30)
            .values('item__name', 'item__unit', 'item__sku')
            .annotate(total_dispensed=Sum('quantity_delta'))
            .order_by('total_dispensed')[:10]
        )

        ctx['total_received_30d'] = (
            StockMovement.objects
            .filter(movement_type=StockMovement.TYPE_RECEIVE, created_at__date__gte=day_30)
            .aggregate(total=Sum('quantity_delta'))['total'] or 0
        )

        ctx['writeoffs_30d'] = (
            StockMovement.objects
            .filter(movement_type=StockMovement.TYPE_WRITEOFF, created_at__date__gte=day_30)
            .aggregate(total=Sum('quantity_delta'))['total'] or 0
        )

        items = ConsumableItem.objects.filter(is_active=True)
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
            trend.append({'date': d.strftime('%d %b'), 'received': received, 'dispensed': dispensed})
        ctx['weekly_trend'] = trend

        all_items = list(ConsumableItem.objects.filter(is_active=True))
        ctx['low_stock_items'] = [
            {'item': item, 'qty': qty_map.get(item.pk, 0)}
            for item in all_items
            if qty_map.get(item.pk, 0) <= item.reorder_level
        ]

        ctx['po_stats'] = (
            PurchaseOrder.objects.values('status').annotate(count=Count('id')).order_by('status')
        )
        ctx['today'] = today
        return ctx


class LowStockAlertView(LoginRequiredMixin, TemplateView):
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