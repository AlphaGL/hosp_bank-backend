from django.db import models
from patients.models import Visit


class DepartmentQueue(models.Model):
    """One queue entry per visit per department."""
    STATUS_WAITING = 'waiting'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_SKIPPED = 'skipped'
    STATUS_CHOICES = [
        (STATUS_WAITING, 'Waiting'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_SKIPPED, 'Skipped'),
    ]

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='queue_entries')
    department = models.CharField(max_length=100)
    queue_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)
    called_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    attended_by = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='attended_queue_entries'
    )
    date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'department', 'queue_number']
        unique_together = ['department', 'date', 'queue_number']

    def __str__(self):
        return f"Q#{self.queue_number} | {self.department} | {self.visit.patient.full_name} | {self.status}"
