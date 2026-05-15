from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView
from django.db.models import Sum, Count, Q
from datetime import timedelta


class DashboardSummaryView(LoginRequiredMixin, TemplateView):
    """
    Replaces DashboardSummaryView (APIView).
    Renders all stats into a template instead of returning JSON.
    """
    template_name = 'dashboard/summary.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        from patients.models import Patient, Visit
        from billing.models import Payment
        from queues.models import DepartmentQueue

        today = timezone.localdate()
        month_start = today.replace(day=1)

        # ── Patient stats ──────────────────────────────────────────────────
        ctx['total_patients'] = Patient.objects.count()
        ctx['patients_today'] = Patient.objects.filter(created_at__date=today).count()

        # ── Visit stats ────────────────────────────────────────────────────
        visits_today = Visit.objects.filter(visit_date=today)
        ctx['total_visits_today'] = visits_today.count()
        ctx['completed_today']    = visits_today.filter(status='completed').count()
        ctx['in_queue_today']     = visits_today.filter(status='in_queue').count()
        ctx['in_progress_today']  = visits_today.filter(status='in_progress').count()
        ctx['emergency_today']    = visits_today.filter(priority='emergency').count()

        # ── Revenue stats ──────────────────────────────────────────────────
        ctx['revenue_today'] = float(
            Payment.objects.filter(status='paid', paid_at__date=today)
            .aggregate(t=Sum('amount_paid'))['t'] or 0
        )
        ctx['revenue_this_month'] = float(
            Payment.objects.filter(status='paid', paid_at__date__gte=month_start)
            .aggregate(t=Sum('amount_paid'))['t'] or 0
        )
        ctx['pending_payments'] = Payment.objects.filter(status='pending').count()
        ctx['pending_amount'] = float(
            Payment.objects.filter(status='pending')
            .aggregate(t=Sum('amount_due'))['t'] or 0
        )

        # ── Queue summary per department ───────────────────────────────────
        ctx['queue_summary'] = list(
            DepartmentQueue.objects.filter(date=today)
            .values('department', 'status')
            .annotate(count=Count('id'))
            .order_by('department')
        )

        # ── 7-day visit + revenue trend ────────────────────────────────────
        trend = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            trend.append({
                'date': d.strftime('%d %b'),
                'visits': Visit.objects.filter(visit_date=d).count(),
                'revenue': float(
                    Payment.objects.filter(paid_at__date=d, status='paid')
                    .aggregate(t=Sum('amount_paid'))['t'] or 0
                ),
            })
        ctx['weekly_trend'] = trend
        ctx['today'] = today

        return ctx


class DepartmentWorkloadView(LoginRequiredMixin, TemplateView):
    """
    Replaces DepartmentWorkloadView (APIView).
    Renders per-department queue workload for today.
    """
    template_name = 'dashboard/workload.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        from queues.models import DepartmentQueue

        today = timezone.localdate()
        ctx['workload'] = list(
            DepartmentQueue.objects
            .filter(date=today)
            .values('department')
            .annotate(
                total=Count('id'),
                waiting=Count('id', filter=Q(status='waiting')),
                in_progress=Count('id', filter=Q(status='in_progress')),
                completed=Count('id', filter=Q(status='completed')),
            )
            .order_by('department')
        )
        ctx['today'] = today
        return ctx