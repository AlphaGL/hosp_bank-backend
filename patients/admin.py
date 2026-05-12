from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Staff, Patient, Visit


@admin.register(Staff)
class StaffAdmin(UserAdmin):
    list_display = ['username', 'get_full_name', 'role', 'department', 'is_active']
    list_filter = ['role', 'is_active', 'department']
    fieldsets = UserAdmin.fieldsets + (
        ('Hospital Info', {'fields': ('role', 'phone', 'department')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Hospital Info', {'fields': ('role', 'phone', 'department', 'first_name', 'last_name')}),
    )


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['patient_id', 'full_name', 'age', 'gender', 'phone', 'created_at']
    search_fields = ['patient_id', 'first_name', 'last_name', 'phone']
    list_filter = ['gender', 'created_at']
    readonly_fields = ['patient_id', 'created_at', 'updated_at']


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'visit_date', 'status', 'priority', 'created_by']
    list_filter = ['status', 'priority', 'visit_date']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__patient_id']
    readonly_fields = ['created_at', 'updated_at']
