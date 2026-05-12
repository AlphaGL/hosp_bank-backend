from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        week_ago = today - timedelta(days=7)
        month_start = today.replace(day=1)

        from patients.models import Patient, Visit
        from billing.models import Payment
        from queues.models import DepartmentQueue

        # Patient stats
        total_patients = Patient.objects.count()
        patients_today = Patient.objects.filter(created_at__date=today).count()

        # Visit stats
        visits_today = Visit.objects.filter(visit_date=today)
        total_visits_today = visits_today.count()
        completed_today = visits_today.filter(status='completed').count()
        in_queue_today = visits_today.filter(status='in_queue').count()
        in_progress_today = visits_today.filter(status='in_progress').count()
        emergency_today = visits_today.filter(priority='emergency').count()

        # Revenue stats
        paid_today = Payment.objects.filter(
            status='paid', paid_at__date=today
        ).aggregate(total=Sum('amount_paid'))['total'] or 0

        paid_this_month = Payment.objects.filter(
            status='paid', paid_at__date__gte=month_start
        ).aggregate(total=Sum('amount_paid'))['total'] or 0

        pending_payments = Payment.objects.filter(status='pending').count()
        pending_amount = Payment.objects.filter(
            status='pending'
        ).aggregate(total=Sum('amount_due'))['total'] or 0

        # Queue summary per department
        queue_summary = list(
            DepartmentQueue.objects.filter(date=today)
            .values('department', 'status')
            .annotate(count=Count('id'))
            .order_by('department')
        )

        # Visit trend (last 7 days)
        trend = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            count = Visit.objects.filter(visit_date=d).count()
            revenue = Payment.objects.filter(paid_at__date=d, status='paid').aggregate(
                t=Sum('amount_paid'))['t'] or 0
            trend.append({
                'date': d.isoformat(),
                'visits': count,
                'revenue': float(revenue),
            })

        return Response({
            'date': today.isoformat(),
            'patients': {
                'total': total_patients,
                'new_today': patients_today,
            },
            'visits': {
                'total_today': total_visits_today,
                'completed': completed_today,
                'in_queue': in_queue_today,
                'in_progress': in_progress_today,
                'emergency': emergency_today,
            },
            'revenue': {
                'today': float(paid_today),
                'this_month': float(paid_this_month),
                'pending_count': pending_payments,
                'pending_amount': float(pending_amount),
            },
            'queue_summary': queue_summary,
            'weekly_trend': trend,
        })


class DepartmentWorkloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        from queues.models import DepartmentQueue
        from django.db.models import Avg, ExpressionWrapper, DurationField, F

        data = (
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
        return Response(list(data))
