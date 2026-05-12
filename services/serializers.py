from rest_framework import serializers
from .models import DiagnosticService, VisitService


class DiagnosticServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosticService
        fields = '__all__'


class VisitServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_code = serializers.CharField(source='service.code', read_only=True)
    department = serializers.CharField(source='service.department', read_only=True)
    attended_by_name = serializers.SerializerMethodField()

    class Meta:
        model = VisitService
        fields = [
            'id', 'visit', 'service', 'service_name', 'service_code', 'department',
            'status', 'price_at_booking', 'notes', 'report',
            'attended_by', 'attended_by_name',
            'started_at', 'completed_at', 'created_at',
        ]
        read_only_fields = ['price_at_booking', 'created_at']

    def get_attended_by_name(self, obj):
        if obj.attended_by:
            return obj.attended_by.get_full_name() or obj.attended_by.username
        return None


class VisitServiceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitService
        fields = ['status', 'notes', 'report', 'attended_by', 'started_at', 'completed_at']
