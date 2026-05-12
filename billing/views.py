from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Payment
from .serializers import PaymentSerializer, PaymentConfirmSerializer
from patients.models import Visit
from patients.permissions import IsFinance, IsAdmin
from notifications.utils import create_notification


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('visit__patient', 'processed_by').all()
    serializer_class = PaymentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'paid_at', 'amount_due']

    def get_permissions(self):
        if self.action in ['confirm_payment', 'create']:
            return [IsFinance()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        date = self.request.query_params.get('date')
        patient_id = self.request.query_params.get('patient')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if date:
            qs = qs.filter(created_at__date=date)
        if patient_id:
            qs = qs.filter(visit__patient__patient_id=patient_id)
        return qs

    def perform_create(self, serializer):
        """Auto-calculate amount_due from visit services."""
        visit = serializer.validated_data['visit']
        amount_due = sum(vs.price_at_booking for vs in visit.visit_services.all())
        serializer.save(amount_due=amount_due, processed_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm_payment(self, request, pk=None):
        payment = self.get_object()

        if payment.status == Payment.STATUS_PAID:
            return Response({'error': 'Payment already confirmed.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PaymentConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        payment.amount_paid = data['amount_paid']
        payment.payment_method = data['payment_method']
        payment.transaction_ref = data.get('transaction_ref', '')
        payment.notes = data.get('notes', '')
        payment.processed_by = request.user
        payment.paid_at = timezone.now()
        payment.status = Payment.STATUS_PAID if payment.is_fully_paid else Payment.STATUS_PENDING
        payment.save()

        if payment.status == Payment.STATUS_PAID:
            # Update visit status & add to queue
            visit = payment.visit
            visit.status = Visit.STATUS_PAID
            visit.save(update_fields=['status'])

            # Auto-add to queue per department
            from queues.utils import add_visit_to_queues
            add_visit_to_queues(visit)

            # Notify front desk
            create_notification(
                event_type='payment_confirmed',
                visit=visit,
                message=f"Payment confirmed for {visit.patient.full_name}. Added to queue.",
            )

        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=['get'], url_path='receipt')
    def receipt(self, request, pk=None):
        payment = self.get_object()
        if payment.status != Payment.STATUS_PAID:
            return Response({'error': 'Receipt only available for paid invoices.'},
                            status=status.HTTP_400_BAD_REQUEST)
        data = PaymentSerializer(payment).data
        data['receipt_generated_at'] = timezone.now().isoformat()
        return Response(data)
