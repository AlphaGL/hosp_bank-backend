from rest_framework import serializers
from .models import DepartmentQueue


class DepartmentQueueSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    patient_id_code = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    attended_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DepartmentQueue
        fields = [
            'id', 'visit', 'patient_name', 'patient_id_code', 'priority',
            'department', 'queue_number', 'status', 'services',
            'called_at', 'completed_at',
            'attended_by', 'attended_by_name', 'date', 'created_at',
        ]
        read_only_fields = ['queue_number', 'date', 'created_at']

    def get_patient_name(self, obj):
        return obj.visit.patient.full_name

    def get_patient_id_code(self, obj):
        return obj.visit.patient.patient_id

    def get_priority(self, obj):
        return obj.visit.priority

    def get_services(self, obj):
        return list(
            obj.visit.visit_services
            .filter(service__department=obj.department)
            .values_list('service__name', flat=True)
        )

    def get_attended_by_name(self, obj):
        if obj.attended_by:
            return obj.attended_by.get_full_name() or obj.attended_by.username
        return None
