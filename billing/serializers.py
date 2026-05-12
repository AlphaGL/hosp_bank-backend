from rest_framework import serializers
from .models import Payment
from patients.serializers import VisitSerializer


class PaymentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    patient_id_code = serializers.SerializerMethodField()
    services_summary = serializers.SerializerMethodField()
    balance = serializers.ReadOnlyField()
    is_fully_paid = serializers.ReadOnlyField()
    processed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id', 'visit', 'receipt_number',
            'patient_name', 'patient_id_code', 'services_summary',
            'amount_due', 'amount_paid', 'balance', 'is_fully_paid',
            'payment_method', 'status', 'transaction_ref',
            'processed_by', 'processed_by_name',
            'paid_at', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['receipt_number', 'amount_due', 'created_at', 'updated_at']

    def get_patient_name(self, obj):
        return obj.visit.patient.full_name

    def get_patient_id_code(self, obj):
        return obj.visit.patient.patient_id

    def get_services_summary(self, obj):
        return [
            {
                'service': vs.service.name,
                'price': str(vs.price_at_booking),
            }
            for vs in obj.visit.visit_services.all()
        ]

    def get_processed_by_name(self, obj):
        if obj.processed_by:
            return obj.processed_by.get_full_name() or obj.processed_by.username
        return None


class PaymentConfirmSerializer(serializers.Serializer):
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=Payment.METHOD_CHOICES)
    transaction_ref = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
