from django.db import models
from django.db.models import Sum
from patients.models import Visit


class Payment(models.Model):
    METHOD_CASH = 'cash'
    METHOD_CARD = 'card'
    METHOD_TRANSFER = 'bank_transfer'
    METHOD_CHOICES = [
        (METHOD_CASH, 'Cash'),
        (METHOD_CARD, 'Card'),
        (METHOD_TRANSFER, 'Bank Transfer'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    visit = models.OneToOneField(Visit, on_delete=models.CASCADE, related_name='payment')
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    transaction_ref = models.CharField(max_length=100, blank=True, help_text='Bank/card transaction reference')
    receipt_number = models.CharField(max_length=30, unique=True, editable=False)
    processed_by = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True, related_name='processed_payments'
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"RCP-{self.receipt_number} | {self.visit.patient.full_name} | {self.status}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            import uuid
            self.receipt_number = f"RCP{uuid.uuid4().hex[:8].upper()}"
        if not self.amount_due:
            self.amount_due = self.calculate_total()
        super().save(*args, **kwargs)

    def calculate_total(self):
        result = self.visit.visit_services.aggregate(total=Sum('price_at_booking'))
        return result['total'] or 0

    @property
    def balance(self):
        return self.amount_due - self.amount_paid

    @property
    def is_fully_paid(self):
        return self.amount_paid >= self.amount_due