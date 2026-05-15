from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, View
)
from django.http import HttpResponse

from .models import Payment
from .forms import PaymentCreateForm, PaymentConfirmForm, PaymentFilterForm
from patients.models import Visit
from notifications.utils import create_notification


# ---------------------------------------------------------------------------
# Permission mixins (replaces DRF IsFinance / IsAuthenticated permission classes)
# ---------------------------------------------------------------------------

class FinanceRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only Finance staff (or admins) may access this view."""
    def test_func(self):
        user = self.request.user
        return user.is_superuser or getattr(user, 'role', None) in ('finance', 'admin')


# ---------------------------------------------------------------------------
# List  (GET /payments/)
# ---------------------------------------------------------------------------

class PaymentListView(LoginRequiredMixin, ListView):
    """
    Replaces: PaymentViewSet.list()
    Supports ?status=, ?date=, ?patient= query params via PaymentFilterForm.
    """
    model = Payment
    template_name = 'payments/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 25
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
        return ctx


# ---------------------------------------------------------------------------
# Detail  (GET /payments/<pk>/)
# ---------------------------------------------------------------------------

class PaymentDetailView(LoginRequiredMixin, DetailView):
    """
    Replaces: PaymentViewSet.retrieve()
    Also provides the PaymentConfirmForm so the confirm action can be
    triggered from the same page.
    """
    model = Payment
    template_name = 'payments/payment_detail.html'
    context_object_name = 'payment'

    def get_queryset(self):
        return Payment.objects.select_related('visit__patient', 'processed_by')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['confirm_form'] = PaymentConfirmForm()
        ctx['services'] = self.object.visit.visit_services.select_related('service').all()
        return ctx


# ---------------------------------------------------------------------------
# Create  (GET+POST /payments/new/)
# ---------------------------------------------------------------------------

class PaymentCreateView(FinanceRequiredMixin, CreateView):
    """
    Replaces: PaymentViewSet.create() + perform_create()
    Auto-calculates amount_due from visit services.
    """
    model = Payment
    form_class = PaymentCreateForm
    template_name = 'payments/payment_form.html'

    def get_success_url(self):
        return reverse('payments:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        visit = form.cleaned_data['visit']
        amount_due = sum(vs.price_at_booking for vs in visit.visit_services.all())
        payment = form.save(commit=False)
        payment.amount_due = amount_due
        payment.processed_by = self.request.user
        payment.save()
        self.object = payment
        messages.success(self.request, f"Payment record created — {payment.receipt_number}")
        return redirect(self.get_success_url())


# ---------------------------------------------------------------------------
# Confirm payment  (POST /payments/<pk>/confirm/)
# ---------------------------------------------------------------------------

class PaymentConfirmView(FinanceRequiredMixin, View):
    """
    Replaces: PaymentViewSet.confirm_payment() custom action.
    POST-only; redirects back to the detail page.
    """
    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)

        if payment.status == Payment.STATUS_PAID:
            messages.error(request, "Payment has already been confirmed.")
            return redirect(reverse('payments:detail', kwargs={'pk': pk}))

        form = PaymentConfirmForm(request.POST)
        if not form.is_valid():
            # Re-render detail page with form errors
            from django.shortcuts import render
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
                f"Partial payment recorded. Outstanding balance: {payment.balance}"
            )

        return redirect(reverse('payments:detail', kwargs={'pk': pk}))


# ---------------------------------------------------------------------------
# Receipt  (GET /payments/<pk>/receipt/)
# ---------------------------------------------------------------------------

class PaymentReceiptView(LoginRequiredMixin, DetailView):
    """
    Replaces: PaymentViewSet.receipt() custom action.
    Renders a print-friendly receipt template for paid invoices.
    """
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