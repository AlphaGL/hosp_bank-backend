from django.db import models
from patients.models import Visit


class Notification(models.Model):
    EVENT_PAYMENT_CONFIRMED = 'payment_confirmed'
    EVENT_PATIENT_QUEUED = 'patient_queued'
    EVENT_DIAGNOSIS_COMPLETED = 'diagnosis_completed'
    EVENT_GENERAL = 'general'

    EVENT_CHOICES = [
        (EVENT_PAYMENT_CONFIRMED, 'Payment Confirmed'),
        (EVENT_PATIENT_QUEUED, 'Patient Queued'),
        (EVENT_DIAGNOSIS_COMPLETED, 'Diagnosis Completed'),
        (EVENT_GENERAL, 'General'),
    ]

    TARGET_ALL = 'all'
    TARGET_RECEPTIONIST = 'receptionist'
    TARGET_FINANCE = 'finance'
    TARGET_DOCTOR = 'doctor'
    TARGET_ADMIN = 'admin'
    TARGET_CHOICES = [
        (TARGET_ALL, 'All Staff'),
        (TARGET_RECEPTIONIST, 'Receptionist'),
        (TARGET_FINANCE, 'Finance'),
        (TARGET_DOCTOR, 'Doctor'),
        (TARGET_ADMIN, 'Admin'),
    ]

    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES, default=EVENT_GENERAL)
    visit = models.ForeignKey(Visit, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    message = models.TextField()
    target_role = models.CharField(max_length=20, choices=TARGET_CHOICES, default=TARGET_ALL)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.event_type}] {self.message[:60]}"


class StaffNotificationRead(models.Model):
    """Track per-staff read status for notifications."""
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='read_by')
    staff = models.ForeignKey('patients.Staff', on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['notification', 'staff']
