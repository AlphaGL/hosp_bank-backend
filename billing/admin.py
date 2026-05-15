from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'visit', 'amount_due', 'amount_paid', 'payment_method', 'status', 'paid_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['receipt_number', 'visit__patient__first_name', 'visit__patient__patient_id']
    readonly_fields = ['receipt_number', 'created_at', 'updated_at']