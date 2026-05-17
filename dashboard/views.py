from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView
from django.db.models import Sum, Count, Q
from datetime import timedelta
from inventory.utils import get_low_stock_items, total_stock_value, get_expiring_batches


class DashboardSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/summary.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        from patients.models import Patient, Visit
        from billing.models import Payment
        from queues.models import DepartmentQueue

        today = timezone.localdate()
        month_start = today.replace(day=1)

        # ── Inventory ─────────────────────────────────────────────────────
        low_stock = get_low_stock_items()
        ctx['low_stock_items']     = low_stock
        ctx['low_stock_count']     = len(low_stock)
        ctx['total_stock_value']   = total_stock_value()
        ctx['expiring_soon_count'] = get_expiring_batches(days=90).count()

        # Pending POs (draft + submitted) for the inventory stat card
        from inventory.models import PurchaseOrder
        ctx['pending_pos'] = PurchaseOrder.objects.filter(
            status__in=[PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SUBMITTED]
        ).count()

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

        # Recent visits (for the table)
        ctx['recent_visits'] = (
            Visit.objects
            .select_related('patient', 'created_by')
            .order_by('-created_at')[:10]
        )

        # Visits that have no services attached (active only)
        try:
            from services.models import VisitService
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
            ctx['visits_without_services'] = []

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

        # ── Services stats ─────────────────────────────────────────────────
        try:
            from services.models import ServiceCatalogue, VisitService
            ctx['total_services']           = ServiceCatalogue.objects.filter(is_active=True).count()
            ctx['pending_service_requests'] = VisitService.objects.filter(status='pending').count()
        except Exception:
            ctx['total_services']           = 0
            ctx['pending_service_requests'] = 0

        # ── Queue summary per department (grouped for sidebar) ─────────────
        raw_queue = list(
            DepartmentQueue.objects.filter(date=today)
            .values('department', 'status')
            .annotate(count=Count('id'))
            .order_by('department')
        )
        # Re-group into {dept: {waiting, in_progress, completed}}
        dept_map = {}
        for row in raw_queue:
            d = row['department']
            if d not in dept_map:
                dept_map[d] = {'department': d, 'waiting': 0, 'in_progress': 0, 'completed': 0}
            status = row['status']
            if status in dept_map[d]:
                dept_map[d][status] = row['count']
        ctx['queue_summary']         = raw_queue          # flat, for workload view
        ctx['queue_summary_grouped'] = list(dept_map.values())  # grouped, for sidebar

        # ── 7-day visit + revenue trend ────────────────────────────────────
        trend = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            visits_count = Visit.objects.filter(visit_date=d).count()
            rev = float(
                Payment.objects.filter(paid_at__date=d, status='paid')
                .aggregate(t=Sum('amount_paid'))['t'] or 0
            )
            trend.append({
                'date': d.strftime('%d %b'),
                'visits': visits_count,
                'revenue': rev,
            })
        ctx['weekly_trend'] = trend

        # Pass max values so the template can scale the trend bars
        ctx['max_visits_this_week']  = max((d['visits']  for d in trend), default=1) or 1
        ctx['max_revenue_this_week'] = max((d['revenue'] for d in trend), default=1) or 1

        ctx['today'] = today
        return ctx


class DepartmentWorkloadView(LoginRequiredMixin, TemplateView):
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