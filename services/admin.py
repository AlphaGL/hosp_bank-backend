from django.contrib import admin
from .models import DiagnosticService, VisitService


@admin.register(DiagnosticService)
class DiagnosticServiceAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'department', 'base_price', 'is_active']
    list_filter = ['category', 'department', 'is_active']
    search_fields = ['name', 'code']


@admin.register(VisitService)
class VisitServiceAdmin(admin.ModelAdmin):
    list_display = ['visit', 'service', 'status', 'price_at_booking', 'attended_by']
    list_filter = ['status']
    search_fields = ['visit__patient__first_name', 'service__name']
