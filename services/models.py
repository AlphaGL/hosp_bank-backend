from django.db import models
from cloudinary.models import CloudinaryField   # ← Cloudinary native field
from patients.models import Visit


class DiagnosticService(models.Model):
    """Master list of available diagnostic services."""
    CATEGORY_IMAGING = 'imaging'
    CATEGORY_LAB = 'lab'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_IMAGING, 'Imaging'),
        (CATEGORY_LAB, 'Laboratory'),
        (CATEGORY_OTHER, 'Other'),
    ]

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_IMAGING)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    department = models.CharField(max_length=100)   # e.g. "Radiology", "Ultrasound"
    duration_minutes = models.PositiveIntegerField(default=30, help_text='Expected duration in minutes')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"[{self.code}] {self.name} — ₦{self.base_price}"


class VisitService(models.Model):
    """Services requested for a specific visit."""
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='visit_services')
    service = models.ForeignKey(DiagnosticService, on_delete=models.PROTECT, related_name='visit_services')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    price_at_booking = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)

    # Stores the diagnostic report (PDF, image, etc.) directly in Cloudinary.
    # upload_to becomes the folder path inside your Cloudinary account.
    # resource_type='auto' lets Cloudinary accept PDFs, images, and other file types.
    report = CloudinaryField(
        'report',
        folder='reports',          # top-level folder in Cloudinary
        resource_type='auto',      # accepts PDF, images, docs, etc.
        blank=True,
        null=True,
    )

    attended_by = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='attended_services'
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['visit', 'service']
        ordering = ['created_at']

    def __str__(self):
        return f"Visit#{self.visit_id} — {self.service.name} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.price_at_booking = self.service.base_price
        super().save(*args, **kwargs)

    @property
    def report_url(self):
        """Returns the secure Cloudinary URL for the report, or None."""
        if self.report:
            return self.report.url
        return None