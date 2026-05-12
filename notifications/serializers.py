from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'event_type', 'visit', 'patient_name', 'message',
                  'target_role', 'is_read', 'created_at']

    def get_patient_name(self, obj):
        if obj.visit:
            return obj.visit.patient.full_name
        return None
