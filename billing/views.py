from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import (
    ListView, DetailView, CreateView, View
)
from django.http import HttpResponse

from .models import Payment, DiscountRequest
from .forms import (
    PaymentCreateForm, PaymentConfirmForm, PaymentFilterForm,
    DiscountRequestForm, DiscountApprovalForm,
)
from patients.models import Visit
from notifications.utils import create_notification


# ---------------------------------------------------------------------------
# Permission mixins
# ---------------------------------------------------------------------------

class FinanceRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only Finance staff (or admins) may access."""
    def test_func(self):
        user = self.request.user
        return user.is_superuser or getattr(user, 'role', None) in ('finance', 'admin')


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only admin staff may access."""
    def test_func(self):
        user = self.request.user
        return user.is_superuser or getattr(user, 'role', None) == 'admin'


# ---------------------------------------------------------------------------
# Unified Billing Page  (GET /payments/)
# ---------------------------------------------------------------------------

class PaymentListView(LoginRequiredMixin, ListView):
    """
    Single-page billing hub:
      - Lists existing payments with filter
      - Inline 'New Payment' form (finance/admin only)
      - Pending discount requests badge count in context
    """
    model = Payment
    template_name = 'payments/billing.html'
    context_object_name = 'payments'
    paginate_by = 20
    ordering = ['-created_at']

    def get_queryset(self):
        qs = (
            Payment.objects
            .select_related('visit__patient', 'processed_by')
            .order_by('-created_at')
        )
        form = PaymentFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('status'):
                qs = qs.filter(status=form.cleaned_data['status'])
            if form.cleaned_data.get('date'):
                qs = qs.filter(created_at__date=form.cleaned_data['date'])
            if form.cleaned_data.get('patient'):
                qs = qs.filter(visit__patient__patient_id=form.cleaned_data['patient'])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = PaymentFilterForm(self.request.GET)

        user = self.request.user
        is_finance_or_admin = (
            user.is_superuser or getattr(user, 'role', None) in ('finance', 'admin')
        )
        ctx['can_create'] = is_finance_or_admin

        if is_finance_or_admin:
            ctx['create_form'] = PaymentCreateForm()

        # Pending discount request count — shown in nav badge for admins
        if user.is_superuser or getattr(user, 'role', None) == 'admin':
            ctx['pending_discount_count'] = DiscountRequest.objects.filter(
                status=DiscountRequest.STATUS_PENDING
            ).count()
        return ctx

    def post(self, request, *args, **kwargs):
        """Handle inline payment creation."""
        user = request.user
        if not (user.is_superuser or getattr(user, 'role', None) in ('finance', 'admin')):
            messages.error(request, "Permission denied.")
            return redirect(reverse('payments:list'))

        form = PaymentCreateForm(request.POST)
        if form.is_valid():
            visit = form.cleaned_data['visit']
            amount_due = sum(vs.price_at_booking for vs in visit.visit_services.all())
            payment = form.save(commit=False)
            payment.amount_due = amount_due
            payment.processed_by = request.user
            payment.save()
            messages.success(request, f"Payment record created — {payment.receipt_number}")
            return redirect(reverse('payments:detail', kwargs={'pk': payment.pk}))

        # Re-render list with form errors
        qs = self.get_queryset()
        ctx = self.get_context_data(object_list=qs)
        ctx['create_form'] = form
        ctx['show_create_form'] = True
        return render(request, self.template_name, ctx)


# ---------------------------------------------------------------------------
# Detail  (GET /payments/<pk>/)
# ---------------------------------------------------------------------------

class PaymentDetailView(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = 'payments/payment_detail.html'
    context_object_name = 'payment'

    def get_queryset(self):
        return Payment.objects.select_related('visit__patient', 'processed_by')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['confirm_form'] = PaymentConfirmForm()
        ctx['services'] = self.object.visit.visit_services.select_related('service').all()

        user = self.request.user
        is_finance_or_admin = (
            user.is_superuser or getattr(user, 'role', None) in ('finance', 'admin')
        )
        is_admin = user.is_superuser or getattr(user, 'role', None) == 'admin'

        # Discount request form — only for unpaid payments, finance/admin only
        if is_finance_or_admin and self.object.status != Payment.STATUS_PAID:
            ctx['discount_form'] = DiscountRequestForm(payment=self.object)

        # Active (pending or approved) discount requests on this payment
        ctx['discount_requests'] = self.object.discount_requests.select_related(
            'requested_by', 'reviewed_by'
        ).order_by('-created_at')

        ctx['pending_discount'] = self.object.discount_requests.filter(
            status=DiscountRequest.STATUS_PENDING
        ).first()

        ctx['approved_discount'] = self.object.discount_requests.filter(
            status=DiscountRequest.STATUS_APPROVED
        ).first()

        ctx['is_admin'] = is_admin
        ctx['is_finance_or_admin'] = is_finance_or_admin
        return ctx


# ---------------------------------------------------------------------------
# Confirm payment  (POST /payments/<pk>/confirm/)
# ---------------------------------------------------------------------------

class PaymentConfirmView(FinanceRequiredMixin, View):
    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)

        if payment.status == Payment.STATUS_PAID:
            messages.error(request, "Payment has already been confirmed.")
            return redirect(reverse('payments:detail', kwargs={'pk': pk}))

        form = PaymentConfirmForm(request.POST)
        if not form.is_valid():
            services = payment.visit.visit_services.select_related('service').all()
            return render(request, 'payments/payment_detail.html', {
                'payment': payment,
                'confirm_form': form,
                'services': services,
            })

        data = form.cleaned_data
        payment.amount_paid = data['amount_paid']
        payment.payment_method = data['payment_method']
        payment.transaction_ref = data.get('transaction_ref', '')
        payment.notes = data.get('notes', '')
        payment.processed_by = request.user
        payment.paid_at = timezone.now()
        payment.status = (
            Payment.STATUS_PAID if payment.is_fully_paid else Payment.STATUS_PENDING
        )
        payment.save()

        if payment.status == Payment.STATUS_PAID:
            visit = payment.visit
            visit.status = Visit.STATUS_PAID
            visit.save(update_fields=['status'])

            from queues.utils import add_visit_to_queues
            add_visit_to_queues(visit)

            create_notification(
                event_type='payment_confirmed',
                visit=visit,
                message=f"Payment confirmed for {visit.patient.full_name}. Added to queue.",
            )
            messages.success(request, "Payment confirmed and patient added to queue.")
        else:
            messages.warning(
                request,
                f"Partial payment recorded. Outstanding balance: ₦{payment.balance}"
            )

        return redirect(reverse('payments:detail', kwargs={'pk': pk}))


# ---------------------------------------------------------------------------
# Receipt  (GET /payments/<pk>/receipt/)
# ---------------------------------------------------------------------------

class PaymentReceiptView(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = 'payments/payment_receipt.html'
    context_object_name = 'payment'

    def get(self, request, *args, **kwargs):
        payment = self.get_object()
        if payment.status != Payment.STATUS_PAID:
            messages.error(request, "Receipt is only available for paid invoices.")
            return redirect(reverse('payments:detail', kwargs={'pk': payment.pk}))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['receipt_generated_at'] = timezone.now()
        ctx['services'] = self.object.visit.visit_services.select_related('service').all()
        return ctx


# ---------------------------------------------------------------------------
# Discount Request  (POST /payments/<pk>/request-discount/)
# ---------------------------------------------------------------------------

class DiscountRequestView(FinanceRequiredMixin, View):
    """
    Finance staff submits a discount request for admin approval.
    Only allowed on unpaid payments with no pending discount already in queue.
    """
    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)

        if payment.status == Payment.STATUS_PAID:
            messages.error(request, "Cannot apply a discount to an already paid invoice.")
            return redirect(reverse('payments:detail', kwargs={'pk': pk}))

        # Block duplicate pending requests
        if payment.discount_requests.filter(status=DiscountRequest.STATUS_PENDING).exists():
            messages.warning(request, "A discount request is already pending admin approval.")
            return redirect(reverse('payments:detail', kwargs={'pk': pk}))

        form = DiscountRequestForm(payment=payment, data=request.POST)
        if form.is_valid():
            dr = form.save(commit=False)
            dr.payment = payment
            dr.requested_by = request.user
            dr.save()

            # Notify admins
            create_notification(
                event_type='general',
                visit=payment.visit,
                message=(
                    f"{request.user.get_full_name()} requested a ₦{dr.discount_amount} discount "
                    f"on payment {payment.receipt_number} for {payment.visit.patient.full_name}. "
                    f"Reason: {dr.reason}"
                ),
                target_role='admin',
            )
            messages.success(
                request,
                f"Discount request of ₦{dr.discount_amount} submitted. "
                f"Awaiting admin approval."
            )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")

        return redirect(reverse('payments:detail', kwargs={'pk': pk}))


# ---------------------------------------------------------------------------
# Discount Approval Queue  (GET/POST /payments/discounts/)
# ---------------------------------------------------------------------------

class DiscountRequestListView(AdminRequiredMixin, ListView):
    """
    Admin-only queue of all discount requests.
    Pending ones are shown first.
    """
    model = DiscountRequest
    template_name = 'payments/discount_requests.html'
    context_object_name = 'discount_requests'
    paginate_by = 25

    def get_queryset(self):
        return (
            DiscountRequest.objects
            .select_related(
                'payment__visit__patient',
                'requested_by',
                'reviewed_by',
            )
            .order_by(
                # pending first, then by newest
                '-status',  # 'pending' > 'rejected' > 'approved' alphabetically — use Case below
            )
        )

    def get_queryset(self):
        from django.db.models import Case, When, IntegerField
        return (
            DiscountRequest.objects
            .select_related('payment__visit__patient', 'requested_by', 'reviewed_by')
            .annotate(
                order=Case(
                    When(status=DiscountRequest.STATUS_PENDING, then=0),
                    When(status=DiscountRequest.STATUS_APPROVED, then=1),
                    When(status=DiscountRequest.STATUS_REJECTED, then=2),
                    default=3,
                    output_field=IntegerField(),
                )
            )
            .order_by('order', '-created_at')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending_count'] = DiscountRequest.objects.filter(
            status=DiscountRequest.STATUS_PENDING
        ).count()
        return ctx


# ---------------------------------------------------------------------------
# Discount Approve / Reject  (POST /payments/discounts/<pk>/review/)
# ---------------------------------------------------------------------------

class DiscountReviewView(AdminRequiredMixin, View):
    """
    Admin approves or rejects a specific discount request.
    On approval, the discount is immediately applied to the payment.
    """
    def post(self, request, pk):
        dr = get_object_or_404(
            DiscountRequest.objects.select_related('payment', 'payment__visit__patient'),
            pk=pk,
        )

        if dr.status != DiscountRequest.STATUS_PENDING:
            messages.error(request, "This request has already been reviewed.")
            return redirect(reverse('payments:discounts'))

        form = DiscountApprovalForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid submission.")
            return redirect(reverse('payments:discounts'))

        action = form.cleaned_data['action']
        reviewer_note = form.cleaned_data.get('reviewer_note', '')

        dr.reviewed_by = request.user
        dr.reviewer_note = reviewer_note
        dr.reviewed_at = timezone.now()

        if action == DiscountApprovalForm.ACTION_APPROVE:
            dr.status = DiscountRequest.STATUS_APPROVED

            # Apply discount to the payment
            payment = dr.payment
            payment.discount_amount = dr.discount_amount
            payment.discount_approved_by = request.user
            payment.save(update_fields=['discount_amount', 'discount_approved_by', 'updated_at'])

            dr.save()

            # Notify finance
            create_notification(
                event_type='general',
                visit=payment.visit,
                message=(
                    f"Admin {request.user.get_full_name()} approved a ₦{dr.discount_amount} "
                    f"discount on {payment.receipt_number}."
                ),
                target_role='finance',
            )
            messages.success(
                request,
                f"Discount of ₦{dr.discount_amount} approved and applied to "
                f"{dr.payment.receipt_number}."
            )

        else:  # reject
            dr.status = DiscountRequest.STATUS_REJECTED
            dr.save()

            create_notification(
                event_type='general',
                visit=dr.payment.visit,
                message=(
                    f"Admin {request.user.get_full_name()} rejected the discount request "
                    f"on {dr.payment.receipt_number}."
                    + (f" Note: {reviewer_note}" if reviewer_note else "")
                ),
                target_role='finance',
            )
            messages.warning(request, f"Discount request rejected.")

        # If coming from payment detail, go back there
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(reverse('payments:discounts'))