from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, View, TemplateView
)

from .models import Staff, Patient, Visit
from .forms import (
    StaffLoginForm, StaffProfileForm,
    StaffCreateForm, StaffUpdateForm,
    PatientForm, PatientSearchForm,
    VisitCreateForm, VisitFilterForm, VisitStatusForm,
)


# ---------------------------------------------------------------------------
# Permission mixins  (replaces DRF permission classes in permissions.py)
# ---------------------------------------------------------------------------

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_admin


class ReceptionistRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return u.is_receptionist or u.is_admin


# ---------------------------------------------------------------------------
# Auth  (replaces auth_views.py: LoginView, LogoutView, StaffProfileView)
# ---------------------------------------------------------------------------

class StaffLoginView(View):
    """Replaces LoginView (APIView). Uses Django's session auth instead of JWT."""
    template_name = 'patients/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('patients:dashboard')
        return render(request, self.template_name, {'form': StaffLoginForm()})

    def post(self, request):
        form = StaffLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, "Account is deactivated. Contact admin.")
                return render(request, self.template_name, {'form': form})
            login(request, user)
            return redirect(request.GET.get('next', reverse('patients:dashboard')))
        return render(request, self.template_name, {'form': form})


class StaffLogoutView(LoginRequiredMixin, View):
    """Replaces LogoutView (APIView). POST to log out (CSRF-safe)."""
    def post(self, request):
        logout(request)
        return redirect(reverse('patients:login'))


class StaffProfileView(LoginRequiredMixin, View):
    """Replaces StaffProfileView GET + PATCH."""
    template_name = 'patients/profile.html'

    def get(self, request):
        return render(request, self.template_name, {
            'form': StaffProfileForm(instance=request.user),
            'staff': request.user,
        })

    def post(self, request):
        form = StaffProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect(reverse('patients:profile'))
        return render(request, self.template_name, {'form': form, 'staff': request.user})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'patients/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # ── Core patient / visit stats ────────────────────────────────────
        today = timezone.now().date()
        ctx['total_patients'] = Patient.objects.count()
        ctx['today_visits'] = Visit.objects.filter(visit_date=today).count()
        ctx['pending_visits'] = Visit.objects.filter(
            status__in=[Visit.STATUS_REGISTERED, Visit.STATUS_AWAITING_PAYMENT]
        ).count()
        ctx['completed_today'] = Visit.objects.filter(
            visit_date=today, status=Visit.STATUS_COMPLETED
        ).count()
        ctx['recent_visits'] = (
            Visit.objects.select_related('patient', 'created_by')
            .order_by('-created_at')[:10]
        )

        # ── Services stats ────────────────────────────────────────────────
        try:
            from services.models import ServiceCatalogue, VisitService
            ctx['total_services'] = ServiceCatalogue.objects.filter(is_active=True).count()
            ctx['pending_service_requests'] = VisitService.objects.filter(status='pending').count()

            visits_with_services = VisitService.objects.values_list('visit_id', flat=True).distinct()
            ctx['visits_without_services'] = (
                Visit.objects
                .filter(visit_date=today)
                .exclude(status__in=['completed', 'cancelled'])
                .exclude(pk__in=visits_with_services)
                .select_related('patient')
                .order_by('-created_at')
            )
        except Exception:
            ctx['total_services'] = 0
            ctx['pending_service_requests'] = 0
            ctx['visits_without_services'] = []

        # ── Inventory stats (pulled via utils so no tight import coupling) ─
        try:
            from inventory.utils import get_low_stock_items, get_expiring_batches
            from inventory.models import ConsumableItem, PurchaseOrder

            low_stock = get_low_stock_items()
            ctx['low_stock_items'] = low_stock
            ctx['low_stock_count'] = len(low_stock)

            ctx['expiring_soon_count'] = get_expiring_batches(days=90).count()

            ctx['inv_total_items'] = ConsumableItem.objects.filter(is_active=True).count()

            ctx['pending_pos'] = PurchaseOrder.objects.filter(
                status__in=[PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SUBMITTED]
            ).count()
        except Exception:
            ctx['low_stock_items'] = []
            ctx['low_stock_count'] = 0
            ctx['expiring_soon_count'] = 0
            ctx['inv_total_items'] = 0
            ctx['pending_pos'] = 0

        return ctx


# ---------------------------------------------------------------------------
# Staff  (replaces StaffViewSet — admin only)
# ---------------------------------------------------------------------------

class StaffListView(AdminRequiredMixin, ListView):
    model = Staff
    template_name = 'patients/staff_list.html'
    context_object_name = 'staff_members'
    paginate_by = 20

    def get_queryset(self):
        qs = Staff.objects.order_by('first_name')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q) | Q(first_name__icontains=q) |
                Q(last_name__icontains=q) | Q(email__icontains=q) |
                Q(role__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class StaffCreateView(AdminRequiredMixin, CreateView):
    model = Staff
    form_class = StaffCreateForm
    template_name = 'patients/staff_form.html'
    success_url = reverse_lazy('patients:staff-list')

    def form_valid(self, form):
        messages.success(self.request, "Staff account created.")
        return super().form_valid(form)


class StaffUpdateView(AdminRequiredMixin, UpdateView):
    model = Staff
    form_class = StaffUpdateForm
    template_name = 'patients/staff_form.html'
    success_url = reverse_lazy('patients:staff-list')

    def form_valid(self, form):
        messages.success(self.request, "Staff account updated.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Patient  (replaces PatientViewSet)
# ---------------------------------------------------------------------------

class PatientListView(LoginRequiredMixin, ListView):
    """Replaces list() + search_patient() custom action."""
    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 25

    def get_queryset(self):
        qs = Patient.objects.select_related('registered_by').order_by('-created_at')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(patient_id__icontains=q) | Q(first_name__icontains=q) |
                Q(last_name__icontains=q) | Q(phone__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_form'] = PatientSearchForm(self.request.GET)
        return ctx


class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = 'patients/patient_detail.html'
    context_object_name = 'patient'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['visits'] = self.object.visits.select_related('created_by').order_by('-created_at')
        return ctx


class PatientCreateView(LoginRequiredMixin, CreateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'

    def get_success_url(self):
        return reverse('patients:patient-detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        patient = form.save(commit=False)
        patient.registered_by = self.request.user
        patient.save()
        self.object = patient
        messages.success(self.request, f"Patient {patient.full_name} registered — {patient.patient_id}")
        return redirect(self.get_success_url())


class PatientUpdateView(LoginRequiredMixin, UpdateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'

    def get_success_url(self):
        return reverse('patients:patient-detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Patient record updated.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Visit  (replaces VisitViewSet)
# ---------------------------------------------------------------------------

class VisitListView(LoginRequiredMixin, ListView):
    model = Visit
    template_name = 'patients/visit_list.html'
    context_object_name = 'visits'
    paginate_by = 25

    def get_queryset(self):
        qs = Visit.objects.select_related('patient', 'created_by').order_by('-created_at')
        form = VisitFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('status'):
                qs = qs.filter(status=form.cleaned_data['status'])
            if form.cleaned_data.get('priority'):
                qs = qs.filter(priority=form.cleaned_data['priority'])
            if form.cleaned_data.get('date'):
                qs = qs.filter(visit_date=form.cleaned_data['date'])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = VisitFilterForm(self.request.GET)
        return ctx


class VisitDetailView(LoginRequiredMixin, DetailView):
    model = Visit
    template_name = 'patients/visit_detail.html'
    context_object_name = 'visit'

    def get_queryset(self):
        return Visit.objects.select_related('patient', 'created_by')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_form'] = VisitStatusForm(initial={'status': self.object.status})
        services = self.object.visit_services.select_related('service').all()
        ctx['services'] = services
        ctx['services_total'] = sum(vs.price_at_booking for vs in services)
        return ctx


class VisitCreateView(LoginRequiredMixin, CreateView):
    model = Visit
    form_class = VisitCreateForm
    template_name = 'patients/visit_form.html'

    def get_success_url(self):
        return reverse('patients:visit-detail', kwargs={'pk': self.object.pk})

    def get_initial(self):
        initial = super().get_initial()
        patient_pk = self.request.GET.get('patient')
        if patient_pk:
            initial['patient'] = patient_pk
        return initial

    def form_valid(self, form):
        visit = form.save(commit=False)
        visit.created_by = self.request.user
        visit.status = Visit.STATUS_AWAITING_PAYMENT
        visit.save()
        self.object = visit
        messages.success(self.request, f"Visit #{visit.pk} created for {visit.patient.full_name}.")
        return redirect(self.get_success_url())


class VisitUpdateStatusView(LoginRequiredMixin, View):
    """
    Replaces VisitViewSet.update_status() custom action.
    POST-only; redirects back to visit detail.
    """
    def post(self, request, pk):
        visit = get_object_or_404(Visit, pk=pk)
        form = VisitStatusForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid status.")
            return redirect(reverse('patients:visit-detail', kwargs={'pk': pk}))

        new_status = form.cleaned_data['status']
        visit.status = new_status
        visit.save(update_fields=['status', 'updated_at'])

        if new_status == Visit.STATUS_COMPLETED:
            from notifications.utils import create_notification
            create_notification(
                event_type='diagnosis_completed',
                visit=visit,
                message=f"Patient {visit.patient.full_name} (Visit #{visit.id}) has completed diagnosis.",
            )
            messages.success(request, "Visit marked complete. Notification sent.")
        else:
            messages.success(request, f"Status updated to '{visit.get_status_display()}'.")

        return redirect(reverse('patients:visit-detail', kwargs={'pk': pk}))