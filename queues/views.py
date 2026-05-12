from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import DepartmentQueue
from .serializers import DepartmentQueueSerializer
from patients.permissions import IsDoctor, IsAdmin


class DepartmentQueueViewSet(viewsets.ModelViewSet):
    queryset = DepartmentQueue.objects.select_related('visit__patient', 'attended_by').all()
    serializer_class = DepartmentQueueSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['queue_number', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        dept = self.request.query_params.get('department')
        status_filter = self.request.query_params.get('status')
        date = self.request.query_params.get('date', str(timezone.localdate()))
        priority = self.request.query_params.get('priority')

        qs = qs.filter(date=date)

        if dept:
            qs = qs.filter(department__icontains=dept)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if priority:
            qs = qs.filter(visit__priority=priority)

        # Doctors auto-filter to their department
        user = self.request.user
        if user.is_doctor and not user.is_admin and user.department:
            qs = qs.filter(department__icontains=user.department)

        return qs

    @action(detail=False, methods=['get'], url_path='live')
    def live_queue(self, request):
        """Real-time view: today's waiting queue, priority first."""
        dept = request.query_params.get('department')
        qs = DepartmentQueue.objects.filter(
            date=timezone.localdate(),
            status=DepartmentQueue.STATUS_WAITING,
        ).order_by('-visit__priority', 'queue_number')

        if dept:
            qs = qs.filter(department__icontains=dept)

        user = request.user
        if user.is_doctor and not user.is_admin and user.department:
            qs = qs.filter(department__icontains=user.department)

        return Response(DepartmentQueueSerializer(qs, many=True).data)

    @action(detail=True, methods=['patch'], url_path='call')
    def call_patient(self, request, pk=None):
        """Mark patient as In Progress (called to room)."""
        entry = self.get_object()
        entry.status = DepartmentQueue.STATUS_IN_PROGRESS
        entry.called_at = timezone.now()
        entry.attended_by = request.user
        entry.save(update_fields=['status', 'called_at', 'attended_by'])
        return Response(DepartmentQueueSerializer(entry).data)

    @action(detail=True, methods=['patch'], url_path='complete')
    def complete(self, request, pk=None):
        entry = self.get_object()
        entry.status = DepartmentQueue.STATUS_COMPLETED
        entry.completed_at = timezone.now()
        entry.save(update_fields=['status', 'completed_at'])
        return Response(DepartmentQueueSerializer(entry).data)

    @action(detail=True, methods=['patch'], url_path='skip')
    def skip(self, request, pk=None):
        entry = self.get_object()
        entry.status = DepartmentQueue.STATUS_SKIPPED
        entry.save(update_fields=['status'])
        return Response(DepartmentQueueSerializer(entry).data)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Department-wise queue summary for today."""
        from django.db.models import Count
        today = timezone.localdate()
        data = (
            DepartmentQueue.objects
            .filter(date=today)
            .values('department', 'status')
            .annotate(count=Count('id'))
            .order_by('department', 'status')
        )
        # Reshape to {dept: {status: count}}
        result = {}
        for row in data:
            dept = row['department']
            if dept not in result:
                result[dept] = {}
            result[dept][row['status']] = row['count']
        return Response(result)
