from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'target_role', 'is_read', 'created_at', 'message']
    list_filter = ['event_type', 'target_role', 'is_read']
