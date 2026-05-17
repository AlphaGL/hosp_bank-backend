"""
sitemap/views.py — MediCore HMS
────────────────────────────────
Views:
  NavigationHubView     — visual sitemap / navigation hub
  PlatformStatsView     — full statistical report (admin + finance)
  ActivityLogView       — activity log browser (admin only)
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from datetime import timedelta, date


# ── Permission mixins ──────────────────────────────────────────────────────

class AdminOrFinanceMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return getattr(u, 'is_admin', False) or getattr(u, 'is_finance', False)


class AdminOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return getattr(self.request.user, 'is_admin', False)


# ── Role label helper ──────────────────────────────────────────────────────

def _role_label(user):
    if getattr(user, 'is_admin', False):
        return ('Administrator', 'Full system access', 'admin')
    parts = []
    for attr, label in [
        ('is_doctor', 'Doctor'), ('is_nurse', 'Nurse'),
        ('is_receptionist', 'Receptionist'), ('is_finance', 'Finance'),
        ('is_pharmacy', 'Pharmacy'), ('is_store_keeper', 'Store Keeper'),
        ('is_lab', 'Lab Tech'),
    ]:
        if getattr(user, attr, False):
            parts.append(label)
    label = ' / '.join(parts) if parts else 'Staff'
    return (label, 'Role-based access active', 'staff')


# ── Navigation Hub ─────────────────────────────────────────────────────────

class NavigationHubView(LoginRequiredMixin, TemplateView):
    template_name = 'sitemap/hub.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        role_label, role_sub, role_type = _role_label(self.request.user)
        ctx['role_label'] = role_label
        ctx['role_sub']   = role_sub
        ctx['role_type']  = role_type
        return ctx


# ── Platform Stats ─────────────────────────────────────────────────────────

class PlatformStatsView(AdminOrFinanceMixin, TemplateView):
    template_name = 'sitemap/stats.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today      = timezone.localdate()
        month_start = today.replace(day=1)
        year_start  = today.replace(month=1, day=1)

        # ── Patients ───────────────────────────────────────────────────────
        try:
            from patients.models import Patient, Visit
            ctx['total_patients']         = Patient.objects.count()
            ctx['patients_this_month']    = Patient.objects.filter(created_at__date__gte=month_start).count()
            ctx['patients_this_year']     = Patient.objects.filter(created_at__date__gte=year_start).count()
            ctx['patients_today']         = Patient.objects.filter(created_at__date=today).count()

            # Visit stats
            ctx['total_visits']           = Visit.objects.count()
            ctx['visits_today']           = Visit.objects.filter(visit_date=today).count()
            ctx['visits_this_month']      = Visit.objects.filter(visit_date__gte=month_start).count()
            ctx['completed_visits']       = Visit.objects.filter(status='completed').count()
            ctx['emergency_visits']       = Visit.objects.filter(priority='emergency').count()
            ctx['cancelled_visits']       = Visit.objects.filter(status='cancelled').count()

            # Visit status breakdown
            ctx['visit_status_breakdown'] = list(
                Visit.objects.values('status')
                .annotate(count=Count('id'))
                .order_by('-count')
            )

            # 30-day visit trend
            visit_trend = []
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                visit_trend.append({
                    'date':   d.strftime('%d %b'),
                    'count':  Visit.objects.filter(visit_date=d).count(),
                })
            ctx['visit_trend'] = visit_trend
            ctx['max_visit_trend'] = max((d['count'] for d in visit_trend), default=1) or 1

        except Exception:
            pass

        # ── Billing ────────────────────────────────────────────────────────
        try:
            from billing.models import Payment
            ctx['total_revenue']          = float(Payment.objects.filter(status='paid').aggregate(t=Sum('amount_paid'))['t'] or 0)
            ctx['revenue_today']          = float(Payment.objects.filter(status='paid', paid_at__date=today).aggregate(t=Sum('amount_paid'))['t'] or 0)
            ctx['revenue_this_month']     = float(Payment.objects.filter(status='paid', paid_at__date__gte=month_start).aggregate(t=Sum('amount_paid'))['t'] or 0)
            ctx['revenue_this_year']      = float(Payment.objects.filter(status='paid', paid_at__date__gte=year_start).aggregate(t=Sum('amount_paid'))['t'] or 0)
            ctx['pending_payments_count'] = Payment.objects.filter(status='pending').count()
            ctx['pending_payments_amount']= float(Payment.objects.filter(status='pending').aggregate(t=Sum('amount_due'))['t'] or 0)
            ctx['failed_payments']        = Payment.objects.filter(status='failed').count()
            ctx['avg_payment']            = float(Payment.objects.filter(status='paid').aggregate(a=Avg('amount_paid'))['a'] or 0)

            # Payment method breakdown
            ctx['payment_method_breakdown'] = list(
                Payment.objects.filter(status='paid')
                .values('payment_method')
                .annotate(count=Count('id'), total=Sum('amount_paid'))
                .order_by('-total')
            )

            # Payment status breakdown
            ctx['payment_status_breakdown'] = list(
                Payment.objects.values('status')
                .annotate(count=Count('id'))
                .order_by('-count')
            )

            # 30-day revenue trend
            rev_trend = []
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                rev = float(Payment.objects.filter(status='paid', paid_at__date=d).aggregate(t=Sum('amount_paid'))['t'] or 0)
                rev_trend.append({'date': d.strftime('%d %b'), 'amount': rev})
            ctx['revenue_trend']     = rev_trend
            ctx['max_revenue_trend'] = max((d['amount'] for d in rev_trend), default=1) or 1

            # Discount stats
            from billing.models import DiscountRequest
            ctx['discount_requests_total']    = DiscountRequest.objects.count()
            ctx['discount_requests_pending']  = DiscountRequest.objects.filter(status='pending').count()
            ctx['discount_requests_approved'] = DiscountRequest.objects.filter(status='approved').count()
            ctx['discount_total_approved']    = float(DiscountRequest.objects.filter(status='approved').aggregate(t=Sum('discount_amount'))['t'] or 0)

        except Exception:
            pass

        # ── Inventory ──────────────────────────────────────────────────────
        try:
            from inventory.models import ConsumableItem, StockMovement, PurchaseOrder, StockBatch
            from inventory.utils import get_low_stock_items, total_stock_value, get_expiring_batches

            ctx['inventory_total_items']    = ConsumableItem.objects.filter(is_active=True).count()
            ctx['inventory_total_value']    = total_stock_value()
            ctx['inventory_low_stock']      = len(get_low_stock_items())
            ctx['inventory_out_of_stock']   = sum(1 for i in get_low_stock_items() if i['is_out'])
            ctx['inventory_expiring_soon']  = get_expiring_batches(days=90).count()
            ctx['inventory_expired']        = StockBatch.objects.filter(expiry_date__lt=today).count()

            # Category breakdown
            ctx['inventory_by_category'] = list(
                ConsumableItem.objects.filter(is_active=True)
                .values('category')
                .annotate(count=Count('id'))
                .order_by('-count')
            )

            # PO stats
            ctx['po_total']     = PurchaseOrder.objects.count()
            ctx['po_pending']   = PurchaseOrder.objects.filter(status__in=['draft', 'submitted']).count()
            ctx['po_received']  = PurchaseOrder.objects.filter(status='received').count()

            # Movement stats (last 30 days)
            ctx['dispenses_this_month'] = StockMovement.objects.filter(
                movement_type='dispense', created_at__date__gte=month_start
            ).count()
            ctx['writeoffs_this_month'] = StockMovement.objects.filter(
                movement_type='writeoff', created_at__date__gte=month_start
            ).count()

        except Exception:
            pass

        # ── Services / Clinical ────────────────────────────────────────────
        try:
            from services.models import DiagnosticService, VisitService
            ctx['services_total']      = DiagnosticService.objects.filter(is_active=True).count()
            ctx['services_pending']    = VisitService.objects.filter(status='pending').count()
            ctx['services_completed']  = VisitService.objects.filter(status='completed').count()
            ctx['services_inprogress'] = VisitService.objects.filter(status='in_progress').count()

            ctx['top_services'] = list(
                VisitService.objects.values('service__name', 'service__category')
                .annotate(count=Count('id'))
                .order_by('-count')[:8]
            )

            ctx['services_by_category'] = list(
                VisitService.objects.values('service__category')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
        except Exception:
            pass

        # ── Staff ──────────────────────────────────────────────────────────
        try:
            from patients.models import Staff
            ctx['staff_total']  = Staff.objects.filter(is_active=True).count()
            ctx['staff_by_role'] = list(
                Staff.objects.filter(is_active=True)
                .values('role')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
        except Exception:
            pass

        # ── Queues ─────────────────────────────────────────────────────────
        try:
            from queues.models import DepartmentQueue
            ctx['queue_today_total']     = DepartmentQueue.objects.filter(date=today).count()
            ctx['queue_today_waiting']   = DepartmentQueue.objects.filter(date=today, status='waiting').count()
            ctx['queue_today_completed'] = DepartmentQueue.objects.filter(date=today, status='completed').count()
            ctx['queue_by_dept'] = list(
                DepartmentQueue.objects.filter(date=today)
                .values('department')
                .annotate(
                    total=Count('id'),
                    waiting=Count('id', filter=Q(status='waiting')),
                    completed=Count('id', filter=Q(status='completed')),
                )
                .order_by('-total')[:8]
            )
        except Exception:
            pass

        ctx['today']       = today
        ctx['month_start'] = month_start
        ctx['generated_at'] = timezone.now()
        return ctx


# ── Activity Log ───────────────────────────────────────────────────────────

class ActivityLogView(AdminOnlyMixin, TemplateView):
    template_name = 'sitemap/activity_log.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from sitemap.models import ActivityLog

        qs = ActivityLog.objects.select_related('actor').order_by('-timestamp')

        # ── Filters from GET params ────────────────────────────────────────
        category = self.request.GET.get('category', '')
        level    = self.request.GET.get('level', '')
        actor_id = self.request.GET.get('actor', '')
        date_str = self.request.GET.get('date', '')
        search   = self.request.GET.get('q', '')

        if category:
            qs = qs.filter(category=category)
        if level:
            qs = qs.filter(level=level)
        if actor_id:
            qs = qs.filter(actor_id=actor_id)
        if date_str:
            try:
                from datetime import datetime
                d = datetime.strptime(date_str, '%Y-%m-%d').date()
                qs = qs.filter(timestamp__date=d)
            except ValueError:
                pass
        if search:
            qs = qs.filter(
                Q(action__icontains=search) |
                Q(description__icontains=search) |
                Q(object_repr__icontains=search)
            )

        # ── Pagination (50 per page) ───────────────────────────────────────
        from django.core.paginator import Paginator
        paginator = Paginator(qs, 50)
        page_num  = self.request.GET.get('page', 1)
        page_obj  = paginator.get_page(page_num)

        ctx['logs']        = page_obj
        ctx['paginator']   = paginator
        ctx['page_obj']    = page_obj

        # Summary counts for the header cards
        today = timezone.localdate()
        ctx['logs_today']        = ActivityLog.objects.filter(timestamp__date=today).count()
        ctx['logs_errors_today'] = ActivityLog.objects.filter(timestamp__date=today, level='error').count()
        ctx['logs_warnings_today'] = ActivityLog.objects.filter(timestamp__date=today, level='warning').count()
        ctx['logs_total']        = ActivityLog.objects.count()

        # Recent activity breakdown by category
        ctx['category_counts'] = list(
            ActivityLog.objects.filter(timestamp__date__gte=today - timedelta(days=7))
            .values('category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Filter options
        ctx['category_choices'] = ActivityLog.CATEGORY_CHOICES
        ctx['level_choices']    = ActivityLog.LEVEL_CHOICES

        # Active filters (for display)
        ctx['filters'] = {
            'category': category,
            'level':    level,
            'date':     date_str,
            'q':        search,
        }

        ctx['today'] = today
        return ctx