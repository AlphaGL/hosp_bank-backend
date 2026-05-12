from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import DiagnosticService, VisitService
from .serializers import DiagnosticServiceSerializer, VisitServiceSerializer, VisitServiceUpdateSerializer
from patients.permissions import IsAdmin, IsDoctor


class DiagnosticServiceViewSet(viewsets.ModelViewSet):
    queryset = DiagnosticService.objects.filter(is_active=True)
    serializer_class = DiagnosticServiceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code', 'category', 'department']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='by-department')
    def by_department(self, request):
        department = request.query_params.get('dept', '')
        services = self.get_queryset().filter(department__icontains=department)
        return Response(DiagnosticServiceSerializer(services, many=True).data)


class VisitServiceViewSet(viewsets.ModelViewSet):
    queryset = VisitService.objects.select_related('visit', 'service', 'attended_by').all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update', 'update_status']:
            return VisitServiceUpdateSerializer
        return VisitServiceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        visit_id = self.request.query_params.get('visit')
        dept = self.request.query_params.get('department')
        status_filter = self.request.query_params.get('status')
        if visit_id:
            qs = qs.filter(visit_id=visit_id)
        if dept:
            qs = qs.filter(service__department__icontains=dept)
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Doctors see only their department's services
        user = self.request.user
        if user.is_doctor and not user.is_admin and user.department:
            qs = qs.filter(service__department__icontains=user.department)
        return qs

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        vs = self.get_object()
        new_status = request.data.get('status')
        valid = [s[0] for s in VisitService.STATUS_CHOICES]
        if new_status not in valid:
            return Response({'error': f'Invalid status. Options: {valid}'},
                            status=status.HTTP_400_BAD_REQUEST)

        vs.status = new_status
        vs.attended_by = request.user

        if new_status == VisitService.STATUS_IN_PROGRESS and not vs.started_at:
            vs.started_at = timezone.now()
        if new_status == VisitService.STATUS_COMPLETED:
            vs.completed_at = timezone.now()
            # Check if all services in visit are done → mark visit completed
            visit = vs.visit
            all_done = not visit.visit_services.exclude(
                status__in=[VisitService.STATUS_COMPLETED, VisitService.STATUS_CANCELLED]
            ).exists()
            if all_done:
                from patients.models import Visit
                visit.status = Visit.STATUS_COMPLETED
                visit.save(update_fields=['status'])

        vs.save()
        return Response(VisitServiceSerializer(vs).data)

    @action(detail=True, methods=['post'], url_path='upload-report')
    def upload_report(self, request, pk=None):
        vs = self.get_object()
        report = request.FILES.get('report')
        if not report:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        vs.report = report
        vs.save(update_fields=['report'])
        return Response({'message': 'Report uploaded.', 'report_url': request.build_absolute_uri(vs.report.url)})
