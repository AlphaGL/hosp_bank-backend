"""
inventory/utils.py
──────────────────
Utility functions that other apps can import to interact with the IMS
without reaching directly into models.

Usage examples
--------------
    # In a view after a procedure is completed:
    from inventory.utils import dispense_items_for_visit

    dispense_items_for_visit(
        visit=visit,
        items=[
            {'sku': 'GLOVE-L', 'quantity': 2},
            {'sku': 'SYRINGE-5ML', 'quantity': 1},
        ],
        performed_by=request.user,
    )
"""

from django.db import transaction
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Batch selection helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_fefo_batch(item):
    """
    First-Expire, First-Out: return the oldest non-expired StockBatch for
    an item, or None if no valid batch exists.
    """
    from django.db.models import Q
    return (
        item.batches
        .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.localdate()))
        .order_by('expiry_date')
        .first()
    )


# ─────────────────────────────────────────────────────────────────────────────
# Programmatic dispense  (called by other apps)
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def dispense_items_for_visit(visit, items, performed_by, department='', notes=''):
    """
    Dispense a list of consumable items against a visit.

    Parameters
    ----------
    visit        : patients.Visit instance
    items        : list of dicts, each with keys:
                     'sku'      (str)  — ConsumableItem.sku
                     'quantity' (int)
    performed_by : patients.Staff instance
    department   : optional department string
    notes        : optional free-text notes

    Returns
    -------
    list of StockMovement objects created

    Raises
    ------
    ValueError  — if an SKU is not found or stock is insufficient
    """
    from .models import ConsumableItem, StockMovement

    movements = []
    for entry in items:
        sku = entry.get('sku', '').strip()
        qty = int(entry.get('quantity', 0))

        if qty <= 0:
            continue

        try:
            item = ConsumableItem.objects.get(sku=sku, is_active=True)
        except ConsumableItem.DoesNotExist:
            raise ValueError(f"Consumable with SKU '{sku}' not found or inactive.")

        if item.quantity_on_hand < qty:
            raise ValueError(
                f"Insufficient stock for '{item.name}' (SKU: {sku}). "
                f"Requested: {qty}, On hand: {item.quantity_on_hand}."
            )

        batch = get_fefo_batch(item)

        m = StockMovement.objects.create(
            item=item,
            batch=batch,
            movement_type=StockMovement.TYPE_DISPENSE,
            quantity_delta=-qty,
            reference=f"VISIT-{visit.pk}",
            department=department or getattr(visit, 'department', ''),
            visit=visit,
            notes=notes,
            performed_by=performed_by,
        )
        movements.append(m)

    return movements


# ─────────────────────────────────────────────────────────────────────────────
# Stock value
# ─────────────────────────────────────────────────────────────────────────────

def total_stock_value():
    """
    Returns the total monetary value of all active items currently in stock.
    Uses item.unit_cost × quantity_on_hand (not batch-weighted average).
    """
    from django.db.models import Sum
    from .models import ConsumableItem, StockMovement

    qty_map = dict(
        StockMovement.objects
        .values('item_id')
        .annotate(total=Sum('quantity_delta'))
        .values_list('item_id', 'total')
    )
    items = ConsumableItem.objects.filter(is_active=True)
    return sum(
        float(item.unit_cost) * max(qty_map.get(item.pk, 0), 0)
        for item in items
    )


# ─────────────────────────────────────────────────────────────────────────────
# Low-stock check (for dashboard widgets in other apps)
# ─────────────────────────────────────────────────────────────────────────────

def get_low_stock_items():
    """
    Returns a list of dicts for every active item at or below its reorder level.
    Suitable for dashboard context.
    """
    from django.db.models import Sum
    from .models import ConsumableItem, StockMovement

    qty_map = dict(
        StockMovement.objects
        .values('item_id')
        .annotate(total=Sum('quantity_delta'))
        .values_list('item_id', 'total')
    )
    result = []
    for item in ConsumableItem.objects.filter(is_active=True):
        qty = qty_map.get(item.pk, 0)
        if qty <= item.reorder_level:
            result.append({
                'item':          item,
                'quantity':      qty,
                'reorder_level': item.reorder_level,
                'is_out':        qty <= 0,
            })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Expiry helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_expiring_batches(days=90):
    """
    Returns StockBatch queryset for items expiring within `days` days.
    """
    from .models import StockBatch
    today = timezone.localdate()
    cutoff = today + timezone.timedelta(days=days)
    return (
        StockBatch.objects
        .filter(expiry_date__gte=today, expiry_date__lte=cutoff)
        .select_related('item', 'supplier')
        .order_by('expiry_date')
    )