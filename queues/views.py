from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView

from .models import DepartmentQueue


class DepartmentQueueListView(LoginRequiredMixin, ListView):
    """GET /queue/?department=&status=&date=&priority="""
    template_name = 'queue/queue_list.html'
    context_object_name = 'entries'
    paginate_by = 25

    def get_queryset(self):
        qs = DepartmentQueue.objects.select_related('visit__patient', 'attended_by')
        params = self.request.GET
        date = params.get('date', str(timezone.localdate()))
        dept = params.get('department')
        status_filter = params.get('status')
        priority = params.get('priority')

        qs = qs.filter(date=date)
        if dept:
            qs = qs.filter(department__icontains=dept)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if priority:
            qs = qs.filter(visit__priority=priority)

        user = self.request.user
        if (getattr(user, 'is_doctor', False)
                and not getattr(user, 'is_admin', False)
                and getattr(user, 'department', None)):
            qs = qs.filter(department__icontains=user.department)

        return qs.order_by('queue_number')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['today'] = timezone.localdate()
        ctx['status_choices'] = DepartmentQueue.STATUS_CHOICES
        ctx['filters'] = self.request.GET
        return ctx


class DepartmentQueueDetailView(LoginRequiredMixin, DetailView):
    """GET /queue/<pk>/"""
    model = DepartmentQueue
    template_name = 'queue/queue_detail.html'
    context_object_name = 'entry'

    def get_queryset(self):
        return DepartmentQueue.objects.select_related('visit__patient', 'attended_by')


class LiveQueueView(LoginRequiredMixin, View):
    """GET /queue/live/?department= — today's waiting entries, priority first."""

    def get(self, request):
        dept = request.GET.get('department')
        qs = DepartmentQueue.objects.select_related(
            'visit__patient', 'attended_by'
        ).filter(
            date=timezone.localdate(),
            status=DepartmentQueue.STATUS_WAITING,
        ).order_by('-visit__priority', 'queue_number')

        if dept:
            qs = qs.filter(department__icontains=dept)

        user = request.user
        if (getattr(user, 'is_doctor', False)
                and not getattr(user, 'is_admin', False)
                and getattr(user, 'department', None)):
            qs = qs.filter(department__icontains=user.department)

        return render(request, 'queue/live_queue.html', {
            'entries': qs,
            'department': dept,
            'today': timezone.localdate(),
        })


class QueueSummaryView(LoginRequiredMixin, View):
    """GET /queue/summary/ — department-wise counts for today."""

    def get(self, request):
        today = timezone.localdate()
        rows = (
            DepartmentQueue.objects
            .filter(date=today)
            .values('department', 'status')
            .annotate(count=Count('id'))
            .order_by('department', 'status')
        )

        summary = {}
        for row in rows:
            dept = row['department']
            summary.setdefault(dept, {})
            summary[dept][row['status']] = row['count']

        all_statuses = [s for s, _ in DepartmentQueue.STATUS_CHOICES]

        return render(request, 'queue/queue_summary.html', {
            'summary': summary,
            'statuses': all_statuses,
            'today': today,
        })


class CallPatientView(LoginRequiredMixin, View):
    """POST /queue/<pk>/call/ — mark In Progress."""

    def post(self, request, pk):
        entry = get_object_or_404(DepartmentQueue, pk=pk)
        entry.status = DepartmentQueue.STATUS_IN_PROGRESS
        entry.called_at = timezone.now()
        entry.attended_by = request.user
        entry.save(update_fields=['status', 'called_at', 'attended_by'])
        return redirect(request.POST.get('next', 'queue:live'))


class CompleteQueueEntryView(LoginRequiredMixin, View):
    """POST /queue/<pk>/complete/"""

    def post(self, request, pk):
        entry = get_object_or_404(DepartmentQueue, pk=pk)
        entry.status = DepartmentQueue.STATUS_COMPLETED
        entry.completed_at = timezone.now()
        entry.save(update_fields=['status', 'completed_at'])
        return redirect(request.POST.get('next', 'queue:live'))


class SkipQueueEntryView(LoginRequiredMixin, View):
    """POST /queue/<pk>/skip/"""

    def post(self, request, pk):
        entry = get_object_or_404(DepartmentQueue, pk=pk)
        entry.status = DepartmentQueue.STATUS_SKIPPED
        entry.save(update_fields=['status'])
        return redirect(request.POST.get('next', 'queue:live'))