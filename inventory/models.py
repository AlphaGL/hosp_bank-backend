from django.db import models
from django.db.models import Sum, F
from django.core.exceptions import ValidationError
from django.utils import timezone


# ---------------------------------------------------------------------------
# Consumable Item  (master catalogue)
# ---------------------------------------------------------------------------

class ConsumableItem(models.Model):
    """
    Master catalogue of every consumable / medical supply the facility stocks.
    One row per SKU — not per physical unit.
    """
    CATEGORY_DRUG = 'drug'
    CATEGORY_REAGENT = 'reagent'
    CATEGORY_SUPPLY = 'supply'          # gloves, syringes, swabs …
    CATEGORY_EQUIPMENT = 'equipment'    # small reusable items tracked here too
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_DRUG,      'Drug / Medication'),
        (CATEGORY_REAGENT,   'Reagent / Chemical'),
        (CATEGORY_SUPPLY,    'General Supply'),
        (CATEGORY_EQUIPMENT, 'Equipment / Device'),
        (CATEGORY_OTHER,     'Other'),
    ]

    UNIT_PIECES  = 'pcs'
    UNIT_VIALS   = 'vials'
    UNIT_BOTTLES = 'bottles'
    UNIT_BOXES   = 'boxes'
    UNIT_PACKS   = 'packs'
    UNIT_LITRES  = 'litres'
    UNIT_ML      = 'ml'
    UNIT_MG      = 'mg'
    UNIT_G       = 'g'
    UNIT_CHOICES = [
        (UNIT_PIECES,  'Pieces'),
        (UNIT_VIALS,   'Vials'),
        (UNIT_BOTTLES, 'Bottles'),
        (UNIT_BOXES,   'Boxes'),
        (UNIT_PACKS,   'Packs'),
        (UNIT_LITRES,  'Litres'),
        (UNIT_ML,      'mL'),
        (UNIT_MG,      'mg'),
        (UNIT_G,       'g'),
    ]

    # Identification
    name            = models.CharField(max_length=200, unique=True)
    sku             = models.CharField(max_length=30, unique=True, help_text='Internal stock-keeping unit code')
    category        = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_SUPPLY)
    unit            = models.CharField(max_length=10, choices=UNIT_CHOICES, default=UNIT_PIECES)
    description     = models.TextField(blank=True)

    # Where it lives
    department      = models.CharField(max_length=100, blank=True, help_text='Primary department that uses this item')
    storage_location = models.CharField(max_length=100, blank=True, help_text='Shelf / cabinet / fridge location')

    # Stock control thresholds
    reorder_level   = models.PositiveIntegerField(
        default=10,
        help_text='Alert is raised when quantity_on_hand falls to or below this number',
    )
    reorder_quantity = models.PositiveIntegerField(
        default=50,
        help_text='Suggested quantity to order when restocking',
    )

    # Pricing (cost price for accounting)
    unit_cost       = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    created_by      = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True,
        related_name='created_consumables',
    )

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Consumable Item'
        verbose_name_plural = 'Consumable Items'

    def __str__(self):
        return f"[{self.sku}] {self.name}"

    # ------------------------------------------------------------------
    # Computed stock quantities  (derived from StockMovement ledger)
    # ------------------------------------------------------------------

    @property
    def quantity_on_hand(self):
        """Live stock count derived from all movement records."""
        result = self.movements.aggregate(total=Sum('quantity_delta'))
        return result['total'] or 0

    @property
    def is_low_stock(self):
        return self.quantity_on_hand <= self.reorder_level

    @property
    def is_out_of_stock(self):
        return self.quantity_on_hand <= 0


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------

class Supplier(models.Model):
    name         = models.CharField(max_length=200, unique=True)
    contact_name = models.CharField(max_length=100, blank=True)
    phone        = models.CharField(max_length=30, blank=True)
    email        = models.EmailField(blank=True)
    address      = models.TextField(blank=True)
    notes        = models.TextField(blank=True)
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Stock Batch  (physical delivery / lot)
# ---------------------------------------------------------------------------

class StockBatch(models.Model):
    """
    Represents a specific delivery / purchase lot of a consumable item.
    Tracks expiry and batch number per delivery.
    Multiple batches can exist for the same item (FEFO — first-expire, first-out).
    """
    item           = models.ForeignKey(ConsumableItem, on_delete=models.CASCADE, related_name='batches')
    supplier       = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='batches')
    batch_number   = models.CharField(max_length=100, blank=True, help_text='Manufacturer batch / lot number')
    quantity_received = models.PositiveIntegerField()
    unit_cost      = models.DecimalField(max_digits=12, decimal_places=2, help_text='Cost per unit for this batch')
    received_date  = models.DateField(default=timezone.localdate)
    expiry_date    = models.DateField(null=True, blank=True)
    notes          = models.TextField(blank=True)
    received_by    = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True,
        related_name='received_batches',
    )
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['expiry_date', 'received_date']
        verbose_name = 'Stock Batch'
        verbose_name_plural = 'Stock Batches'

    def __str__(self):
        exp = self.expiry_date.strftime('%b %Y') if self.expiry_date else 'No expiry'
        return f"{self.item.name} | Batch {self.batch_number or self.pk} | Exp: {exp}"

    def clean(self):
        if self.expiry_date and self.expiry_date < self.received_date:
            raise ValidationError("Expiry date cannot be before the received date.")

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date < timezone.localdate()
        return False

    @property
    def days_to_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - timezone.localdate()).days
        return None

    @property
    def is_expiring_soon(self, threshold_days=90):
        d = self.days_to_expiry
        return d is not None and 0 <= d <= threshold_days


# ---------------------------------------------------------------------------
# Stock Movement  (the audit ledger — every change in quantity lives here)
# ---------------------------------------------------------------------------

class StockMovement(models.Model):
    """
    Immutable ledger of every quantity change for a consumable item.
    quantity_delta is SIGNED:
        positive  →  stock added   (receive, return, adjustment up)
        negative  →  stock removed (dispense, write-off, adjustment down)
    """
    TYPE_RECEIVE    = 'receive'      # new stock in from supplier
    TYPE_DISPENSE   = 'dispense'     # issued to a visit / patient
    TYPE_ADJUST_UP  = 'adjust_up'   # manual correction — add
    TYPE_ADJUST_DOWN = 'adjust_down' # manual correction — remove
    TYPE_RETURN     = 'return'       # returned from dept back to store
    TYPE_WRITEOFF   = 'writeoff'     # expired / damaged / lost
    TYPE_TRANSFER   = 'transfer'     # moved between departments

    TYPE_CHOICES = [
        (TYPE_RECEIVE,     'Stock Received'),
        (TYPE_DISPENSE,    'Dispensed'),
        (TYPE_ADJUST_UP,   'Adjustment (Add)'),
        (TYPE_ADJUST_DOWN, 'Adjustment (Remove)'),
        (TYPE_RETURN,      'Returned'),
        (TYPE_WRITEOFF,    'Written Off'),
        (TYPE_TRANSFER,    'Inter-department Transfer'),
    ]

    # Positive movement types (quantity_delta must be > 0)
    POSITIVE_TYPES = {TYPE_RECEIVE, TYPE_ADJUST_UP, TYPE_RETURN, TYPE_TRANSFER}
    # Negative movement types (quantity_delta stored as negative)
    NEGATIVE_TYPES = {TYPE_DISPENSE, TYPE_ADJUST_DOWN, TYPE_WRITEOFF}

    item           = models.ForeignKey(ConsumableItem, on_delete=models.CASCADE, related_name='movements')
    batch          = models.ForeignKey(StockBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements')
    movement_type  = models.CharField(max_length=20, choices=TYPE_CHOICES)
    quantity_delta = models.IntegerField(
        help_text='Signed change: positive = stock added, negative = stock removed',
    )
    reference      = models.CharField(max_length=100, blank=True, help_text='PO number, visit ID, etc.')
    department     = models.CharField(max_length=100, blank=True, help_text='Department involved in this movement')
    visit          = models.ForeignKey(
        'patients.Visit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_movements',
        help_text='Set when movement is tied to a patient visit (dispense)',
    )
    notes          = models.TextField(blank=True)
    performed_by   = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True,
        related_name='stock_movements',
    )
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'

    def __str__(self):
        sign = '+' if self.quantity_delta > 0 else ''
        return (
            f"{self.item.name} | {self.get_movement_type_display()} | "
            f"{sign}{self.quantity_delta} {self.item.unit}"
        )

    def clean(self):
        # Enforce sign convention
        if self.movement_type in self.NEGATIVE_TYPES and self.quantity_delta > 0:
            raise ValidationError(
                f"Movement type '{self.get_movement_type_display()}' must have a negative quantity_delta."
            )
        if self.movement_type in self.POSITIVE_TYPES and self.quantity_delta < 0:
            raise ValidationError(
                f"Movement type '{self.get_movement_type_display()}' must have a positive quantity_delta."
            )
        # Guard against negative stock (best-effort — race conditions possible at DB level)
        if self.quantity_delta < 0 and not self.pk:
            current = self.item.quantity_on_hand if self.item_id else 0
            if current + self.quantity_delta < 0:
                raise ValidationError(
                    f"Insufficient stock. On hand: {current} {self.item.unit}."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------

class PurchaseOrder(models.Model):
    """
    Formal order raised to a supplier.
    When the order is marked RECEIVED, StockBatch + StockMovement records
    are created automatically via the view.
    """
    STATUS_DRAFT     = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_RECEIVED  = 'received'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT,     'Draft'),
        (STATUS_SUBMITTED, 'Submitted to Supplier'),
        (STATUS_RECEIVED,  'Received'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    po_number    = models.CharField(max_length=30, unique=True, editable=False)
    supplier     = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    ordered_date = models.DateField(default=timezone.localdate)
    expected_delivery = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    notes        = models.TextField(blank=True)
    raised_by    = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True,
        related_name='raised_purchase_orders',
    )
    received_by  = models.ForeignKey(
        'patients.Staff', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='received_purchase_orders',
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'

    def __str__(self):
        return f"PO-{self.po_number} | {self.supplier.name} | {self.status}"

    def save(self, *args, **kwargs):
        if not self.po_number:
            import uuid
            self.po_number = f"PO{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def total_cost(self):
        return self.lines.aggregate(
            total=Sum(F('quantity_ordered') * F('unit_cost'))
        )['total'] or 0


class PurchaseOrderLine(models.Model):
    """One line item inside a PurchaseOrder."""
    order          = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    item           = models.ForeignKey(ConsumableItem, on_delete=models.PROTECT, related_name='po_lines')
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_cost      = models.DecimalField(max_digits=12, decimal_places=2)
    batch_number   = models.CharField(max_length=100, blank=True)
    expiry_date    = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ['order', 'item']
        verbose_name = 'PO Line'

    def __str__(self):
        return f"{self.order.po_number} — {self.item.name} × {self.quantity_ordered}"

    @property
    def line_total(self):
        return self.quantity_ordered * self.unit_cost