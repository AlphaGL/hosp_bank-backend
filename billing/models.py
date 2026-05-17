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

    # Discount fields — populated once a DiscountRequest is approved
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Approved discount deducted from amount_due',
    )
    discount_approved_by = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_payment_discounts',
    )

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
    def effective_amount_due(self):
        """Amount due after any approved discount."""
        return max(self.amount_due - self.discount_amount, 0)

    @property
    def balance(self):
        return self.effective_amount_due - self.amount_paid

    @property
    def is_fully_paid(self):
        return self.amount_paid >= self.effective_amount_due


class DiscountRequest(models.Model):
    """
    A finance staff member requests a discount for a Payment.
    An admin must approve or reject it before it takes effect.
    """
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name='discount_requests',
    )
    requested_by = models.ForeignKey(
        'patients.Staff', on_delete=models.CASCADE, related_name='requested_discounts',
    )
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Flat discount amount in naira',
    )
    reason = models.TextField(help_text='Justification for the discount')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_discounts',
    )
    reviewer_note = models.TextField(blank=True, help_text='Admin note when approving or rejecting')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"Discount ₦{self.discount_amount} on {self.payment.receipt_number} "
            f"[{self.get_status_display()}]"
        )