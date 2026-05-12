from rest_framework import serializers
from .models import Staff, Patient, Visit


class StaffSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name',
                  'email', 'role', 'phone', 'department', 'is_active', 'date_joined']
        read_only_fields = ['date_joined']

    def get_full_name(self, obj):
        return obj.get_full_name()


class StaffCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = Staff
        fields = ['username', 'first_name', 'last_name', 'email',
                  'password', 'role', 'phone', 'department']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = Staff(**validated_data)
        user.set_password(password)
        user.save()
        return user


class PatientSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    registered_by_name = serializers.SerializerMethodField()
    total_visits = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id', 'patient_id', 'first_name', 'last_name', 'full_name',
            'age', 'gender', 'phone', 'email', 'address',
            'registered_by', 'registered_by_name', 'total_visits',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['patient_id', 'created_at', 'updated_at', 'registered_by']

    def get_registered_by_name(self, obj):
        if obj.registered_by:
            return obj.registered_by.get_full_name() or obj.registered_by.username
        return None

    def get_total_visits(self, obj):
        return obj.visits.count()


class VisitSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    patient_id_code = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Visit
        fields = [
            'id', 'patient', 'patient_name', 'patient_id_code',
            'visit_date', 'status', 'priority', 'notes',
            'services', 'payment_status',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['visit_date', 'created_at', 'updated_at', 'created_by']

    def get_patient_name(self, obj):
        return obj.patient.full_name

    def get_patient_id_code(self, obj):
        return obj.patient.patient_id

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_services(self, obj):
        from services.serializers import VisitServiceSerializer
        return VisitServiceSerializer(obj.visit_services.all(), many=True).data

    def get_payment_status(self, obj):
        payment = getattr(obj, 'payment', None)
        if payment:
            return payment.status
        return 'not_created'
