from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib import messages

from .models import DiagnosticService, VisitService
from .forms import DiagnosticServiceForm, VisitServiceForm, VisitServiceUpdateForm


# ─────────────────────────────────────────────
# Mixins
# ─────────────────────────────────────────────

class AdminRequiredMixin(UserPassesTestMixin):
    """Only admin users may pass."""
    def test_func(self):
        return getattr(self.request.user, 'is_admin', False)


class DoctorFilterMixin:
    """Automatically narrows a queryset to the logged-in doctor's department."""
    def apply_doctor_filter(self, qs):
        user = self.request.user
        if (getattr(user, 'is_doctor', False)
                and not getattr(user, 'is_admin', False)
                and getattr(user, 'department', None)):
            qs = qs.filter(service__department__icontains=user.department)
        return qs


# ─────────────────────────────────────────────
# DiagnosticService views  (catalogue/)
# ─────────────────────────────────────────────

class DiagnosticServiceListView(LoginRequiredMixin, ListView):
    """GET /catalogue/?q=&dept="""
    template_name = 'services/catalogue_list.html'
    context_object_name = 'services'
    paginate_by = 25

    def get_queryset(self):
        qs = DiagnosticService.objects.filter(is_active=True)
        q = self.request.GET.get('q')
        dept = self.request.GET.get('dept')
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(code__icontains=q) \
                 | qs.filter(category__icontains=q) | qs.filter(department__icontains=q)
        if dept:
            qs = qs.filter(department__icontains=dept)
        return qs.order_by('category', 'name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filters'] = self.request.GET
        ctx['is_admin'] = getattr(self.request.user, 'is_admin', False)
        return ctx


class DiagnosticServiceDetailView(LoginRequiredMixin, DetailView):
    """GET /catalogue/<pk>/"""
    model = DiagnosticService
    template_name = 'services/catalogue_detail.html'
    context_object_name = 'service'


class DiagnosticServiceCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """GET/POST /catalogue/create/"""
    model = DiagnosticService
    form_class = DiagnosticServiceForm
    template_name = 'services/catalogue_form.html'
    success_url = reverse_lazy('services:catalogue-list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Add Diagnostic Service'
        return ctx


class DiagnosticServiceUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """GET/POST /catalogue/<pk>/edit/"""
    model = DiagnosticService
    form_class = DiagnosticServiceForm
    template_name = 'services/catalogue_form.html'
    success_url = reverse_lazy('services:catalogue-list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = f'Edit — {self.object.name}'
        return ctx


class DiagnosticServiceDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """POST /catalogue/<pk>/delete/"""
    model = DiagnosticService
    template_name = 'services/catalogue_confirm_delete.html'
    success_url = reverse_lazy('services:catalogue-list')


class ServicesByDepartmentView(LoginRequiredMixin, View):
    """GET /catalogue/by-department/?dept="""
    template_name = 'services/by_department.html'

    def get(self, request):
        dept = request.GET.get('dept', '')
        services = DiagnosticService.objects.filter(
            is_active=True,
            department__icontains=dept,
        ).order_by('category', 'name')
        return render(request, self.template_name, {
            'services': services,
            'dept': dept,
        })


# ─────────────────────────────────────────────
# VisitService views  (visit-services/)
# ─────────────────────────────────────────────

class VisitServiceListView(LoginRequiredMixin, DoctorFilterMixin, ListView):
    """GET /visit-services/?visit=&department=&status="""
    template_name = 'services/visit_service_list.html'
    context_object_name = 'visit_services'
    paginate_by = 25

    def get_queryset(self):
        qs = VisitService.objects.select_related(
            'visit__patient', 'service', 'attended_by'
        )
        params = self.request.GET
        if params.get('visit'):
            qs = qs.filter(visit_id=params['visit'])
        if params.get('department'):
            qs = qs.filter(service__department__icontains=params['department'])
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        return self.apply_doctor_filter(qs).order_by('created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = VisitService.STATUS_CHOICES
        ctx['filters'] = self.request.GET
        return ctx


class VisitServiceDetailView(LoginRequiredMixin, DetailView):
    """GET /visit-services/<pk>/"""
    template_name = 'services/visit_service_detail.html'
    context_object_name = 'vs'

    def get_queryset(self):
        return VisitService.objects.select_related(
            'visit__patient', 'service', 'attended_by'
        )


class VisitServiceCreateView(LoginRequiredMixin, CreateView):
    """GET/POST /visit-services/create/"""
    model = VisitService
    form_class = VisitServiceForm
    template_name = 'services/visit_service_form.html'

    def get_success_url(self):
        return reverse('services:visit-service-detail', kwargs={'pk': self.object.pk})

    def get_initial(self):
        initial = super().get_initial()
        visit_id = self.request.GET.get('visit')
        if visit_id:
            initial['visit'] = visit_id
        return initial


class VisitServiceUpdateView(LoginRequiredMixin, UpdateView):
    """GET/POST /visit-services/<pk>/edit/"""
    model = VisitService
    form_class = VisitServiceUpdateForm
    template_name = 'services/visit_service_form.html'

    def get_success_url(self):
        return reverse('services:visit-service-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = f'Update — {self.object.service.name}'
        return ctx


class UpdateVisitServiceStatusView(LoginRequiredMixin, View):
    """POST /visit-services/<pk>/update-status/"""

    def post(self, request, pk):
        vs = get_object_or_404(VisitService, pk=pk)
        new_status = request.POST.get('status')
        valid = [s[0] for s in VisitService.STATUS_CHOICES]

        if new_status not in valid:
            messages.error(request, f'Invalid status. Options: {valid}')
            return redirect(request.POST.get('next', reverse('services:visit-service-detail', kwargs={'pk': pk})))

        vs.status = new_status
        vs.attended_by = request.user

        if new_status == VisitService.STATUS_IN_PROGRESS and not vs.started_at:
            vs.started_at = timezone.now()

        if new_status == VisitService.STATUS_COMPLETED:
            vs.completed_at = timezone.now()
            # If all services on this visit are done, mark the visit complete
            visit = vs.visit
            all_done = not visit.visit_services.exclude(
                status__in=[VisitService.STATUS_COMPLETED, VisitService.STATUS_CANCELLED]
            ).exists()
            if all_done:
                from patients.models import Visit
                visit.status = Visit.STATUS_COMPLETED
                visit.save(update_fields=['status'])

        vs.save()
        messages.success(request, f'Status updated to {vs.get_status_display()}.')
        return redirect(request.POST.get('next', reverse('services:visit-service-detail', kwargs={'pk': pk})))


class UploadReportView(LoginRequiredMixin, View):
    """POST /visit-services/<pk>/upload-report/"""

    def post(self, request, pk):
        vs = get_object_or_404(VisitService, pk=pk)
        report = request.FILES.get('report')

        if not report:
            messages.error(request, 'No file provided.')
            return redirect(reverse('services:visit-service-detail', kwargs={'pk': pk}))

        vs.report = report
        vs.save(update_fields=['report'])
        messages.success(request, 'Report uploaded successfully.')
        return redirect(
            request.POST.get('next', reverse('services:visit-service-detail', kwargs={'pk': pk}))
        )