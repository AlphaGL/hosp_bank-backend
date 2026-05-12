import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


# ---------------------------------------------------------------------------
# Custom User / Staff
# ---------------------------------------------------------------------------
class Staff(AbstractUser):
    ROLE_RECEPTIONIST = 'receptionist'
    ROLE_FINANCE = 'finance'
    ROLE_DOCTOR = 'doctor'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_RECEPTIONIST, 'Receptionist'),
        (ROLE_FINANCE, 'Finance Staff'),
        (ROLE_DOCTOR, 'Doctor / Technician'),
        (ROLE_ADMIN, 'Admin'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_RECEPTIONIST)
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Staff'
        verbose_name_plural = 'Staff Members'

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    @property
    def is_receptionist(self):
        return self.role == self.ROLE_RECEPTIONIST

    @property
    def is_finance(self):
        return self.role == self.ROLE_FINANCE

    @property
    def is_doctor(self):
        return self.role == self.ROLE_DOCTOR

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------
def generate_patient_id():
    """Generates a short, human-readable patient ID like PAT-00042."""
    last = Patient.objects.order_by('id').last()
    next_num = (last.id + 1) if last else 1
    return f"PAT-{next_num:05d}"


class Patient(models.Model):
    GENDER_MALE = 'M'
    GENDER_FEMALE = 'F'
    GENDER_OTHER = 'O'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
        (GENDER_OTHER, 'Other'),
    ]

    patient_id = models.CharField(max_length=20, unique=True, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    registered_by = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, null=True, related_name='registered_patients'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.patient_id:
            self.patient_id = generate_patient_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient_id} — {self.full_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


# ---------------------------------------------------------------------------
# Visit  (one patient can have many visits)
# ---------------------------------------------------------------------------
class Visit(models.Model):
    STATUS_REGISTERED = 'registered'
    STATUS_AWAITING_PAYMENT = 'awaiting_payment'
    STATUS_PAID = 'paid'
    STATUS_IN_QUEUE = 'in_queue'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_REGISTERED, 'Registered'),
        (STATUS_AWAITING_PAYMENT, 'Awaiting Payment'),
        (STATUS_PAID, 'Paid'),
        (STATUS_IN_QUEUE, 'In Queue'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    PRIORITY_NORMAL = 'normal'
    PRIORITY_EMERGENCY = 'emergency'
    PRIORITY_CHOICES = [
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_EMERGENCY, 'Emergency'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='visits')
    visit_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REGISTERED)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, null=True, related_name='created_visits'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Visit #{self.pk} — {self.patient.full_name} [{self.status}]"
