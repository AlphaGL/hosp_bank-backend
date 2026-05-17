"""
sitemap/models.py — MediCore HMS
──────────────────────────────────
ActivityLog: immutable audit ledger for every meaningful action on the platform.

Written to by the ActivityLogMiddleware automatically, and also by the
log_activity() helper which views can call explicitly for richer context.

Never edit or delete rows — this is an append-only audit trail.
"""

from django.db import models
from django.utils import timezone


class ActivityLog(models.Model):

    # ── Action categories ──────────────────────────────────────────────────
    CAT_AUTH        = 'auth'
    CAT_PATIENT     = 'patient'
    CAT_VISIT       = 'visit'
    CAT_BILLING     = 'billing'
    CAT_INVENTORY   = 'inventory'
    CAT_STAFF       = 'staff'
    CAT_SERVICES    = 'services'
    CAT_QUEUE       = 'queue'
    CAT_SYSTEM      = 'system'
    CAT_DISCOUNT    = 'discount'

    CATEGORY_CHOICES = [
        (CAT_AUTH,      'Authentication'),
        (CAT_PATIENT,   'Patient'),
        (CAT_VISIT,     'Visit'),
        (CAT_BILLING,   'Billing'),
        (CAT_INVENTORY, 'Inventory'),
        (CAT_STAFF,     'Staff'),
        (CAT_SERVICES,  'Services'),
        (CAT_QUEUE,     'Queue'),
        (CAT_SYSTEM,    'System'),
        (CAT_DISCOUNT,  'Discount'),
    ]

    # ── Severity levels ────────────────────────────────────────────────────
    LEVEL_INFO    = 'info'
    LEVEL_SUCCESS = 'success'
    LEVEL_WARNING = 'warning'
    LEVEL_ERROR   = 'error'

    LEVEL_CHOICES = [
        (LEVEL_INFO,    'Info'),
        (LEVEL_SUCCESS, 'Success'),
        (LEVEL_WARNING, 'Warning'),
        (LEVEL_ERROR,   'Error'),
    ]

    # ── Fields ─────────────────────────────────────────────────────────────
    actor       = models.ForeignKey(
        'patients.Staff',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='activity_logs',
        help_text='Staff member who performed the action (null = system/anonymous)',
    )
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CAT_SYSTEM, db_index=True)
    level       = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    action      = models.CharField(max_length=200, help_text='Short human-readable action label')
    description = models.TextField(blank=True, help_text='Longer detail if needed')

    # Generic link to any object (optional)
    object_type = models.CharField(max_length=50, blank=True, help_text='Model name, e.g. "Patient"')
    object_id   = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=200, blank=True, help_text='String representation of the object')

    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=300, blank=True)
    timestamp   = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['-timestamp', 'category']),
            models.Index(fields=['actor', '-timestamp']),
        ]

    def __str__(self):
        actor = self.actor.get_full_name() if self.actor else 'System'
        return f"[{self.get_category_display()}] {actor} — {self.action}"

    # Prevent accidental edits
    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("ActivityLog entries are immutable — never update, only insert.")
        super().save(*args, **kwargs)