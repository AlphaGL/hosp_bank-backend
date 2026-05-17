from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ConsumableItem, Supplier, StockBatch,
    StockMovement, PurchaseOrder, PurchaseOrderLine,
)


@admin.register(ConsumableItem)
class ConsumableItemAdmin(admin.ModelAdmin):
    list_display  = ['sku', 'name', 'category', 'department', 'unit_cost',
                     'quantity_on_hand_display', 'reorder_level', 'stock_status', 'is_active']
    list_filter   = ['category', 'department', 'is_active']
    search_fields = ['name', 'sku', 'department']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    ordering      = ['category', 'name']

    def quantity_on_hand_display(self, obj):
        return f"{obj.quantity_on_hand} {obj.unit}"
    quantity_on_hand_display.short_description = 'On Hand'

    def stock_status(self, obj):
        if obj.is_out_of_stock:
            return format_html('<span style="color:red;font-weight:bold">OUT OF STOCK</span>')
        if obj.is_low_stock:
            return format_html('<span style="color:orange;font-weight:bold">LOW</span>')
        return format_html('<span style="color:green">OK</span>')
    stock_status.short_description = 'Status'


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display  = ['name', 'contact_name', 'phone', 'email', 'is_active']
    search_fields = ['name', 'contact_name', 'phone']
    list_filter   = ['is_active']


class StockMovementInline(admin.TabularInline):
    model  = StockMovement
    extra  = 0
    fields = ['movement_type', 'quantity_delta', 'reference', 'performed_by', 'created_at']
    readonly_fields = ['created_at']
    can_delete = False


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display  = ['item', 'batch_number', 'supplier', 'quantity_received',
                     'unit_cost', 'received_date', 'expiry_date', 'is_expired']
    list_filter   = ['supplier', 'received_date']
    search_fields = ['item__name', 'batch_number', 'supplier__name']
    readonly_fields = ['created_at']
    ordering      = ['expiry_date']
    inlines       = [StockMovementInline]

    def is_expired(self, obj):
        if obj.is_expired:
            return format_html('<span style="color:red">EXPIRED</span>')
        return format_html('<span style="color:green">Valid</span>')
    is_expired.short_description = 'Expiry Status'


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display  = ['item', 'movement_type', 'quantity_delta', 'reference',
                     'department', 'performed_by', 'created_at']
    list_filter   = ['movement_type', 'created_at']
    search_fields = ['item__name', 'item__sku', 'reference', 'department']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    def has_change_permission(self, request, obj=None):
        """Movements are an immutable audit ledger — no editing after creation."""
        return False


class PurchaseOrderLineInline(admin.TabularInline):
    model  = PurchaseOrderLine
    extra  = 1
    fields = ['item', 'quantity_ordered', 'quantity_received', 'unit_cost', 'batch_number', 'expiry_date']


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display  = ['po_number', 'supplier', 'status', 'ordered_date',
                     'expected_delivery', 'received_date', 'raised_by', 'total_cost']
    list_filter   = ['status', 'supplier']
    search_fields = ['po_number', 'supplier__name']
    readonly_fields = ['po_number', 'created_at', 'updated_at']
    inlines       = [PurchaseOrderLineInline]