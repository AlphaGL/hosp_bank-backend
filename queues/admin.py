from django.contrib import admin
from .models import DepartmentQueue


@admin.register(DepartmentQueue)
class DepartmentQueueAdmin(admin.ModelAdmin):
    list_display = ['queue_number', 'department', 'visit', 'status', 'date', 'attended_by']
    list_filter = ['department', 'status', 'date']
    search_fields = ['visit__patient__first_name', 'department']
    ordering = ['date', 'department', 'queue_number']
