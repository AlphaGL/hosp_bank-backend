from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import Patient, Visit, Staff
from .serializers import PatientSerializer, VisitSerializer, StaffSerializer, StaffCreateSerializer
from .permissions import IsAdmin, IsReceptionistOrAdmin


class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all().order_by('first_name')
    permission_classes = [IsAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'first_name', 'last_name', 'email', 'role']

    def get_serializer_class(self):
        if self.action == 'create':
            return StaffCreateSerializer
        return StaffSerializer


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['patient_id', 'first_name', 'last_name', 'phone']
    ordering_fields = ['created_at', 'first_name', 'last_name']

    def perform_create(self, serializer):
        serializer.save(registered_by=self.request.user)

    @action(detail=True, methods=['get'])
    def visits(self, request, pk=None):
        patient = self.get_object()
        visits = patient.visits.all()
        serializer = VisitSerializer(visits, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='search')
    def search_patient(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response({'results': []})
        patients = Patient.objects.filter(
            Q(patient_id__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(phone__icontains=query)
        )
        serializer = PatientSerializer(patients, many=True)
        return Response({'results': serializer.data})


class VisitViewSet(viewsets.ModelViewSet):
    queryset = Visit.objects.select_related('patient', 'created_by').all()
    serializer_class = VisitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'visit_date', 'priority']

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        priority = self.request.query_params.get('priority')
        date = self.request.query_params.get('date')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if priority:
            qs = qs.filter(priority=priority)
        if date:
            qs = qs.filter(visit_date=date)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status=Visit.STATUS_AWAITING_PAYMENT)

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        visit = self.get_object()
        new_status = request.data.get('status')
        valid = [s[0] for s in Visit.STATUS_CHOICES]
        if new_status not in valid:
            return Response({'error': f'Invalid status. Choose from {valid}'},
                            status=status.HTTP_400_BAD_REQUEST)
        visit.status = new_status
        visit.save(update_fields=['status', 'updated_at'])

        # Trigger notification on completion
        if new_status == Visit.STATUS_COMPLETED:
            from notifications.utils import create_notification
            create_notification(
                event_type='diagnosis_completed',
                visit=visit,
                message=f"Patient {visit.patient.full_name} (Visit #{visit.id}) has completed diagnosis.",
            )

        serializer = VisitSerializer(visit)
        return Response(serializer.data)
