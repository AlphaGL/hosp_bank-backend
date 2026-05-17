from django import forms
from django.core.exceptions import ValidationError
from .models import (
    ConsumableItem, Supplier, StockBatch,
    StockMovement, PurchaseOrder, PurchaseOrderLine,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared widget helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fc(extra=''):
    return {'class': f'form-control {extra}'.strip()}

def _fs(extra=''):
    return {'class': f'form-select {extra}'.strip()}


# ─────────────────────────────────────────────────────────────────────────────
# ConsumableItem
# ─────────────────────────────────────────────────────────────────────────────

class ConsumableItemForm(forms.ModelForm):
    class Meta:
        model = ConsumableItem
        fields = [
            'name', 'sku', 'category', 'unit', 'description',
            'department', 'storage_location',
            'reorder_level', 'reorder_quantity', 'unit_cost',
            'is_active',
        ]
        widgets = {
            'name':             forms.TextInput(attrs=_fc()),
            'sku':              forms.TextInput(attrs=_fc()),
            'category':         forms.Select(attrs=_fs()),
            'unit':             forms.Select(attrs=_fs()),
            'description':      forms.Textarea(attrs={**_fc(), 'rows': 3}),
            'department':       forms.TextInput(attrs=_fc()),
            'storage_location': forms.TextInput(attrs=_fc()),
            'reorder_level':    forms.NumberInput(attrs=_fc()),
            'reorder_quantity':  forms.NumberInput(attrs=_fc()),
            'unit_cost':        forms.NumberInput(attrs={**_fc(), 'step': '0.01'}),
            'is_active':        forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ConsumableItemFilterForm(forms.Form):
    CATEGORY_BLANK = [('', 'All Categories')] + ConsumableItem.CATEGORY_CHOICES

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={**_fc('form-control-sm'), 'placeholder': 'Name or SKU…'}),
    )
    category = forms.ChoiceField(
        choices=CATEGORY_BLANK, required=False,
        widget=forms.Select(attrs=_fs('form-select-sm')),
    )
    department = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={**_fc('form-control-sm'), 'placeholder': 'Department…'}),
    )
    low_stock = forms.BooleanField(
        required=False,
        label='Low stock only',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Supplier
# ─────────────────────────────────────────────────────────────────────────────

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_name', 'phone', 'email', 'address', 'notes', 'is_active']
        widgets = {
            'name':         forms.TextInput(attrs=_fc()),
            'contact_name': forms.TextInput(attrs=_fc()),
            'phone':        forms.TextInput(attrs=_fc()),
            'email':        forms.EmailInput(attrs=_fc()),
            'address':      forms.Textarea(attrs={**_fc(), 'rows': 3}),
            'notes':        forms.Textarea(attrs={**_fc(), 'rows': 3}),
            'is_active':    forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ─────────────────────────────────────────────────────────────────────────────
# StockBatch  (manual batch registration, separate from PO receive flow)
# ─────────────────────────────────────────────────────────────────────────────

class StockBatchForm(forms.ModelForm):
    class Meta:
        model = StockBatch
        fields = [
            'item', 'supplier', 'batch_number',
            'quantity_received', 'unit_cost',
            'received_date', 'expiry_date', 'notes',
        ]
        widgets = {
            'item':              forms.Select(attrs=_fs()),
            'supplier':          forms.Select(attrs=_fs()),
            'batch_number':      forms.TextInput(attrs=_fc()),
            'quantity_received': forms.NumberInput(attrs=_fc()),
            'unit_cost':         forms.NumberInput(attrs={**_fc(), 'step': '0.01'}),
            'received_date':     forms.DateInput(attrs={**_fc(), 'type': 'date'}),
            'expiry_date':       forms.DateInput(attrs={**_fc(), 'type': 'date'}),
            'notes':             forms.Textarea(attrs={**_fc(), 'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        received = cleaned.get('received_date')
        expiry = cleaned.get('expiry_date')
        if received and expiry and expiry < received:
            raise ValidationError("Expiry date cannot be before the received date.")
        return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# StockMovement  (manual dispense / adjustment / writeoff / transfer / return)
# ─────────────────────────────────────────────────────────────────────────────

class StockDispenseForm(forms.Form):
    """
    Used when dispensing items to a visit or department.
    The view converts quantity → negative delta automatically.
    """
    item = forms.ModelChoiceField(
        queryset=ConsumableItem.objects.filter(is_active=True),
        widget=forms.Select(attrs=_fs()),
    )
    batch = forms.ModelChoiceField(
        queryset=StockBatch.objects.none(),   # populated via JS or set in view
        required=False,
        widget=forms.Select(attrs=_fs()),
        help_text='Leave blank to auto-select oldest non-expired batch (FEFO)',
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs=_fc()),
    )
    department = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs=_fc()),
    )
    reference = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs=_fc()),
        help_text='Visit ID, ward reference, etc.',
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={**_fc(), 'rows': 2}),
    )

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get('item')
        qty = cleaned.get('quantity')
        if item and qty:
            if item.quantity_on_hand < qty:
                raise ValidationError(
                    f"Insufficient stock for {item.name}. "
                    f"On hand: {item.quantity_on_hand} {item.unit}."
                )
        return cleaned


class StockAdjustmentForm(forms.Form):
    """
    Manual stock correction — admin / store keeper only.
    Accepts a signed delta directly.
    """
    ADJUST_TYPE_CHOICES = [
        (StockMovement.TYPE_ADJUST_UP,   'Adjustment — Add Stock'),
        (StockMovement.TYPE_ADJUST_DOWN, 'Adjustment — Remove Stock'),
        (StockMovement.TYPE_WRITEOFF,    'Write-off (expired / damaged)'),
        (StockMovement.TYPE_RETURN,      'Return to Store'),
        (StockMovement.TYPE_TRANSFER,    'Inter-department Transfer'),
    ]

    item = forms.ModelChoiceField(
        queryset=ConsumableItem.objects.filter(is_active=True),
        widget=forms.Select(attrs=_fs()),
    )
    movement_type = forms.ChoiceField(
        choices=ADJUST_TYPE_CHOICES,
        widget=forms.Select(attrs=_fs()),
    )
    quantity = forms.IntegerField(
        min_value=1,
        label='Quantity (absolute)',
        widget=forms.NumberInput(attrs=_fc()),
        help_text='Always enter a positive number; the direction is set by the movement type.',
    )
    batch = forms.ModelChoiceField(
        queryset=StockBatch.objects.none(),
        required=False,
        widget=forms.Select(attrs=_fs()),
    )
    department = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs=_fc()),
    )
    reference = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs=_fc()),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={**_fc(), 'rows': 2}),
    )

    def clean(self):
        cleaned = super().clean()
        movement_type = cleaned.get('movement_type')
        item = cleaned.get('item')
        qty = cleaned.get('quantity')

        if movement_type in StockMovement.NEGATIVE_TYPES and item and qty:
            if item.quantity_on_hand < qty:
                raise ValidationError(
                    f"Cannot remove {qty} {item.unit} from {item.name}. "
                    f"On hand: {item.quantity_on_hand} {item.unit}."
                )
        return cleaned


class StockMovementFilterForm(forms.Form):
    TYPE_BLANK = [('', 'All Types')] + StockMovement.TYPE_CHOICES

    item = forms.ModelChoiceField(
        queryset=ConsumableItem.objects.filter(is_active=True),
        required=False,
        empty_label='All Items',
        widget=forms.Select(attrs=_fs('form-select-sm')),
    )
    movement_type = forms.ChoiceField(
        choices=TYPE_BLANK, required=False,
        widget=forms.Select(attrs=_fs('form-select-sm')),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={**_fc('form-control-sm'), 'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={**_fc('form-control-sm'), 'type': 'date'}),
    )
    department = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={**_fc('form-control-sm'), 'placeholder': 'Department…'}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Purchase Order
# ─────────────────────────────────────────────────────────────────────────────

class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'ordered_date', 'expected_delivery', 'notes']
        widgets = {
            'supplier':          forms.Select(attrs=_fs()),
            'ordered_date':      forms.DateInput(attrs={**_fc(), 'type': 'date'}),
            'expected_delivery': forms.DateInput(attrs={**_fc(), 'type': 'date'}),
            'notes':             forms.Textarea(attrs={**_fc(), 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)


class PurchaseOrderLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = ['item', 'quantity_ordered', 'unit_cost', 'batch_number', 'expiry_date']
        widgets = {
            'item':             forms.Select(attrs=_fs()),
            'quantity_ordered': forms.NumberInput(attrs=_fc()),
            'unit_cost':        forms.NumberInput(attrs={**_fc(), 'step': '0.01'}),
            'batch_number':     forms.TextInput(attrs=_fc()),
            'expiry_date':      forms.DateInput(attrs={**_fc(), 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = ConsumableItem.objects.filter(is_active=True)


# Inline formset used on the PO create / edit page
PurchaseOrderLineFormSet = forms.inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class POReceiveForm(forms.Form):
    """
    Simple confirmation form shown when marking a PO as received.
    Allows overriding the received date; the view does the heavy lifting.
    """
    received_date = forms.DateField(
        widget=forms.DateInput(attrs={**_fc(), 'type': 'date'}),
        initial=None,
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={**_fc(), 'rows': 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        self.fields['received_date'].initial = timezone.localdate()


class PurchaseOrderFilterForm(forms.Form):
    STATUS_BLANK = [('', 'All Statuses')] + PurchaseOrder.STATUS_CHOICES

    status = forms.ChoiceField(
        choices=STATUS_BLANK, required=False,
        widget=forms.Select(attrs=_fs('form-select-sm')),
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label='All Suppliers',
        widget=forms.Select(attrs=_fs('form-select-sm')),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={**_fc('form-control-sm'), 'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={**_fc('form-control-sm'), 'type': 'date'}),
    )