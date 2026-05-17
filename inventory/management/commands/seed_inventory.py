"""
seed_inventory.py
─────────────────
Populates the inventory app with realistic sample data.

Usage (run from your Django project root):
    python manage.py shell < seed_inventory.py

Or as a standalone management command runner:
    python manage.py runscript seed_inventory   # if django-extensions is installed

Requirements: your Django project must be configured and migrations applied.
The script is idempotent — re-running it skips records that already exist.
"""

import os
import sys
import django

# ── If running via `python seed_inventory.py` directly, bootstrap Django ──
# Comment this block out if you run via `manage.py shell < seed_inventory.py`
if __name__ == '__main__':
    # Adjust 'myproject.settings' to your actual settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
    django.setup()

# ─────────────────────────────────────────────────────────────────────────────

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

# Lazy imports so Django is set up first
from inventory.models import (
    ConsumableItem, Supplier, StockBatch,
    StockMovement, PurchaseOrder, PurchaseOrderLine,
)

User = get_user_model()

TODAY = timezone.localdate()


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def days(n):
    return timezone.timedelta(days=n)


def log(msg):
    print(f"  ✔  {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Staff / superuser  (needed for FK fields)
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_staff():
    """
    Returns a Staff instance (or a plain User if your Staff model IS the user model).
    Adjust this function to match your `patients.Staff` model.
    """
    # Try to get the Staff model from patients app
    try:
        from patients.models import Staff
        staff, created = Staff.objects.get_or_create(
            username='store_admin',
            defaults={
                'first_name': 'Store',
                'last_name': 'Admin',
                'email': 'store@clinic.local',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            staff.set_password('Admin1234!')
            staff.save()
            log("Created Staff user: store_admin / Admin1234!")
        else:
            log("Staff user 'store_admin' already exists.")
        return staff
    except Exception:
        # Fallback: use the regular User model
        user, created = User.objects.get_or_create(
            username='store_admin',
            defaults={
                'first_name': 'Store',
                'last_name': 'Admin',
                'email': 'store@clinic.local',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            user.set_password('Admin1234!')
            user.save()
            log("Created superuser: store_admin / Admin1234!")
        else:
            log("User 'store_admin' already exists.")
        return user


# ─────────────────────────────────────────────────────────────────────────────
# 2. Suppliers
# ─────────────────────────────────────────────────────────────────────────────

SUPPLIERS = [
    {
        'name': 'MedLine Nigeria Ltd',
        'contact_name': 'Chukwuemeka Obi',
        'phone': '+234-801-234-5678',
        'email': 'orders@medline.ng',
        'address': '12 Industrial Avenue, Apapa, Lagos',
        'notes': 'Primary drug and reagent supplier. Delivers Tuesdays & Fridays.',
        'is_active': True,
    },
    {
        'name': 'HealthPlus Distributors',
        'contact_name': 'Adaeze Nwosu',
        'phone': '+234-802-345-6789',
        'email': 'sales@healthplus.ng',
        'address': '7 Trade Road, Onitsha, Anambra',
        'notes': 'Good source for general consumables and PPE.',
        'is_active': True,
    },
    {
        'name': 'PharmaCare Supplies',
        'contact_name': 'Ibrahim Musa',
        'phone': '+234-803-456-7890',
        'email': 'procurement@pharmacare.ng',
        'address': '45 Ahmadu Bello Way, Abuja',
        'notes': 'Specialises in cold-chain medications.',
        'is_active': True,
    },
    {
        'name': 'LabTech International',
        'contact_name': 'Grace Eze',
        'phone': '+234-804-567-8901',
        'email': 'info@labtech.ng',
        'address': '3 Science Park, Enugu',
        'notes': 'Sole supplier of automated analyser reagents.',
        'is_active': True,
    },
    {
        'name': 'OldSupply Co (Inactive)',
        'contact_name': 'Defunct Contact',
        'phone': '+234-800-000-0000',
        'email': 'none@old.ng',
        'address': 'Closed',
        'notes': 'No longer operational.',
        'is_active': False,
    },
]


def seed_suppliers():
    created_count = 0
    suppliers = {}
    for data in SUPPLIERS:
        obj, created = Supplier.objects.get_or_create(
            name=data['name'],
            defaults=data,
        )
        suppliers[obj.name] = obj
        if created:
            created_count += 1
    log(f"Suppliers: {created_count} created, {len(SUPPLIERS) - created_count} already existed.")
    return suppliers


# ─────────────────────────────────────────────────────────────────────────────
# 3. Consumable Items
# ─────────────────────────────────────────────────────────────────────────────

ITEMS = [
    # ── Drugs ──
    dict(name='Amoxicillin 500mg Capsules', sku='DRUG-AMOX500', category='drug',
         unit='packs', department='Pharmacy', storage_location='Drug Cabinet A1',
         reorder_level=20, reorder_quantity=100, unit_cost=1500.00,
         description='Broad-spectrum antibiotic. Keep in cool, dry place.'),
    dict(name='Paracetamol 500mg Tablets', sku='DRUG-PARA500', category='drug',
         unit='packs', department='Pharmacy', storage_location='Drug Cabinet A2',
         reorder_level=30, reorder_quantity=200, unit_cost=350.00,
         description='Analgesic and antipyretic.'),
    dict(name='Metronidazole 200mg Tablets', sku='DRUG-METRO200', category='drug',
         unit='packs', department='Pharmacy', storage_location='Drug Cabinet A3',
         reorder_level=15, reorder_quantity=80, unit_cost=900.00),
    dict(name='Artesunate Injection 60mg', sku='DRUG-ARTS60', category='drug',
         unit='vials', department='Emergency', storage_location='Emergency Drug Fridge',
         reorder_level=10, reorder_quantity=50, unit_cost=2800.00,
         description='Severe malaria treatment. Refrigerate.'),
    dict(name='IV Fluid Normal Saline 1L', sku='DRUG-NS1L', category='drug',
         unit='bottles', department='Ward', storage_location='IV Fluid Store',
         reorder_level=40, reorder_quantity=200, unit_cost=750.00),
    dict(name='Insulin Regular 10mL Vial', sku='DRUG-INS10', category='drug',
         unit='vials', department='Pharmacy', storage_location='Drug Fridge Shelf 1',
         reorder_level=8, reorder_quantity=30, unit_cost=4500.00,
         description='Cold chain. Store at 2–8 °C.'),

    # ── Reagents ──
    dict(name='Malaria RDT Kit', sku='REAG-MRDTKIT', category='reagent',
         unit='boxes', department='Laboratory', storage_location='Lab Reagent Shelf R1',
         reorder_level=10, reorder_quantity=50, unit_cost=2200.00,
         description='Rapid diagnostic test for P. falciparum.'),
    dict(name='Blood Glucose Strips (50s)', sku='REAG-BGS50', category='reagent',
         unit='boxes', department='Laboratory', storage_location='Lab Shelf R2',
         reorder_level=15, reorder_quantity=60, unit_cost=3500.00),
    dict(name='Urine Dipstick 10-parameter', sku='REAG-UDIP10', category='reagent',
         unit='boxes', department='Laboratory', storage_location='Lab Shelf R3',
         reorder_level=10, reorder_quantity=40, unit_cost=2800.00),
    dict(name='HIV Test Kit (Determine)', sku='REAG-HIVDET', category='reagent',
         unit='boxes', department='Laboratory', storage_location='Lab Fridge R1',
         reorder_level=8, reorder_quantity=30, unit_cost=5500.00),
    dict(name='Haematology Analyser Reagent 5L', sku='REAG-HAEM5L', category='reagent',
         unit='litres', department='Laboratory', storage_location='Lab Analyser Store',
         reorder_level=5, reorder_quantity=20, unit_cost=18000.00,
         description='Proprietary reagent for Sysmex KX-21 analyser.'),

    # ── General Supplies ──
    dict(name='Latex Examination Gloves — Large (100s)', sku='SUPP-GLOVEL', category='supply',
         unit='boxes', department='All', storage_location='PPE Storeroom S1',
         reorder_level=20, reorder_quantity=100, unit_cost=4500.00),
    dict(name='Latex Examination Gloves — Medium (100s)', sku='SUPP-GLOVEM', category='supply',
         unit='boxes', department='All', storage_location='PPE Storeroom S1',
         reorder_level=20, reorder_quantity=100, unit_cost=4500.00),
    dict(name='Surgical Face Mask (50s)', sku='SUPP-FMASK50', category='supply',
         unit='boxes', department='All', storage_location='PPE Storeroom S2',
         reorder_level=15, reorder_quantity=80, unit_cost=2500.00),
    dict(name='Disposable Syringe 5mL', sku='SUPP-SYR5', category='supply',
         unit='boxes', department='All', storage_location='Supply Room S3',
         reorder_level=30, reorder_quantity=150, unit_cost=1800.00,
         description='100 units per box.'),
    dict(name='Disposable Syringe 10mL', sku='SUPP-SYR10', category='supply',
         unit='boxes', department='All', storage_location='Supply Room S3',
         reorder_level=20, reorder_quantity=100, unit_cost=2100.00),
    dict(name='IV Cannula 20G', sku='SUPP-IVC20', category='supply',
         unit='boxes', department='Ward', storage_location='Supply Room S4',
         reorder_level=10, reorder_quantity=50, unit_cost=3200.00,
         description='50 units per box.'),
    dict(name='Cotton Wool Roll 500g', sku='SUPP-COT500', category='supply',
         unit='pcs', department='All', storage_location='Supply Room S5',
         reorder_level=10, reorder_quantity=40, unit_cost=850.00),
    dict(name='Gauze Swabs 7.5cm×7.5cm (100s)', sku='SUPP-GAUZE', category='supply',
         unit='packs', department='Theatre/Wound Care', storage_location='Supply Room S5',
         reorder_level=10, reorder_quantity=50, unit_cost=1200.00),
    dict(name='Adhesive Plaster Roll 2.5cm', sku='SUPP-PLAST', category='supply',
         unit='pcs', department='All', storage_location='Supply Room S5',
         reorder_level=12, reorder_quantity=50, unit_cost=650.00),
    dict(name='Urine Sample Cup (50s)', sku='SUPP-UCUP50', category='supply',
         unit='packs', department='Laboratory', storage_location='Lab Supply Shelf',
         reorder_level=8, reorder_quantity=30, unit_cost=1500.00),
    dict(name='EDTA Blood Collection Tube (100s)', sku='SUPP-EDTA', category='supply',
         unit='boxes', department='Laboratory', storage_location='Lab Supply Shelf',
         reorder_level=8, reorder_quantity=30, unit_cost=3800.00),

    # ── Equipment ──
    dict(name='Digital Thermometer', sku='EQUIP-DTHERM', category='equipment',
         unit='pcs', department='All', storage_location='Equipment Cupboard E1',
         reorder_level=5, reorder_quantity=15, unit_cost=2500.00),
    dict(name='Pulse Oximeter (fingertip)', sku='EQUIP-POXIM', category='equipment',
         unit='pcs', department='Emergency/Ward', storage_location='Equipment Cupboard E1',
         reorder_level=3, reorder_quantity=10, unit_cost=12000.00),
    dict(name='Blood Pressure Cuff (adult)', sku='EQUIP-BPCUFF', category='equipment',
         unit='pcs', department='OPD', storage_location='Equipment Cupboard E2',
         reorder_level=2, reorder_quantity=5, unit_cost=18000.00),

    # ── Other ──
    dict(name='Hand Sanitiser 500mL', sku='OTHER-HSAN500', category='other',
         unit='bottles', department='All', storage_location='Various',
         reorder_level=20, reorder_quantity=100, unit_cost=1200.00),
    dict(name='Sharps Disposal Container 5L', sku='OTHER-SHARP5', category='other',
         unit='pcs', department='All', storage_location='Waste Room',
         reorder_level=5, reorder_quantity=20, unit_cost=1800.00),
]


def seed_items(staff):
    created_count = 0
    items = {}
    for data in ITEMS:
        obj, created = ConsumableItem.objects.get_or_create(
            sku=data['sku'],
            defaults={**data, 'created_by': staff},
        )
        items[obj.sku] = obj
        if created:
            created_count += 1
    log(f"ConsumableItems: {created_count} created, {len(ITEMS) - created_count} already existed.")
    return items


# ─────────────────────────────────────────────────────────────────────────────
# 4. Stock Batches + initial receive movements
# ─────────────────────────────────────────────────────────────────────────────

def seed_batches(items, suppliers, staff):
    """
    Creates multiple batches per item with varied expiry dates (some expiring soon,
    one already expired) to exercise dashboard alerts.
    """
    batches_data = [
        # (sku, supplier_name, batch_no, qty, cost, received_offset_days, expiry_offset_days)
        # Drugs
        ('DRUG-AMOX500',  'MedLine Nigeria Ltd',    'BN-AMOX-001', 120, 1500.00, -90,  +365),
        ('DRUG-AMOX500',  'MedLine Nigeria Ltd',    'BN-AMOX-002',  60, 1450.00, -30,  +180),
        ('DRUG-PARA500',  'HealthPlus Distributors','BN-PARA-001', 200,  350.00, -60,  +400),
        ('DRUG-METRO200', 'MedLine Nigeria Ltd',    'BN-METRO-001', 80,  900.00, -45,  +300),
        ('DRUG-ARTS60',   'PharmaCare Supplies',    'BN-ARTS-001',  40, 2800.00, -10,   +60),  # expiring soon
        ('DRUG-ARTS60',   'PharmaCare Supplies',    'BN-ARTS-002',  20, 2900.00, -5,   +365),
        ('DRUG-NS1L',     'HealthPlus Distributors','BN-NS-001',   200,  750.00, -30,  +500),
        ('DRUG-INS10',    'PharmaCare Supplies',    'BN-INS-001',   20, 4500.00, -20,   +30),  # expiring very soon
        ('DRUG-INS10',    'PharmaCare Supplies',    'BN-INS-002',   10, 4600.00, -5,   +180),
        # Expired batch
        ('DRUG-AMOX500',  'MedLine Nigeria Ltd',    'BN-AMOX-EXP',  10, 1400.00, -400, -15),  # expired 15 days ago

        # Reagents
        ('REAG-MRDTKIT',  'LabTech International',  'BN-MRDT-001',  60, 2200.00, -30,  +180),
        ('REAG-BGS50',    'LabTech International',  'BN-BGS-001',   50, 3500.00, -20,  +365),
        ('REAG-UDIP10',   'LabTech International',  'BN-UDIP-001',  40, 2800.00, -25,  +270),
        ('REAG-HIVDET',   'LabTech International',  'BN-HIV-001',   30, 5500.00, -15,   +75),  # expiring soon
        ('REAG-HAEM5L',   'LabTech International',  'BN-HAEM-001',  15,18000.00, -10,  +365),

        # Supplies
        ('SUPP-GLOVEL',   'HealthPlus Distributors','BN-GLVL-001', 100, 4500.00, -60, None),
        ('SUPP-GLOVEM',   'HealthPlus Distributors','BN-GLVM-001', 100, 4500.00, -60, None),
        ('SUPP-FMASK50',  'HealthPlus Distributors','BN-MASK-001',  80, 2500.00, -45, None),
        ('SUPP-SYR5',     'MedLine Nigeria Ltd',    'BN-SYR5-001', 150, 1800.00, -30, None),
        ('SUPP-SYR10',    'MedLine Nigeria Ltd',    'BN-SYR10-001',100, 2100.00, -30, None),
        ('SUPP-IVC20',    'MedLine Nigeria Ltd',    'BN-IVC-001',   50, 3200.00, -20, None),
        ('SUPP-COT500',   'HealthPlus Distributors','BN-COT-001',   40,  850.00, -50, None),
        ('SUPP-GAUZE',    'HealthPlus Distributors','BN-GAUZ-001',  50, 1200.00, -40, None),
        ('SUPP-PLAST',    'HealthPlus Distributors','BN-PLAS-001',  50,  650.00, -40, None),
        ('SUPP-UCUP50',   'MedLine Nigeria Ltd',    'BN-UCUP-001',  30, 1500.00, -15, None),
        ('SUPP-EDTA',     'LabTech International',  'BN-EDTA-001',  30, 3800.00, -10, None),

        # Equipment (no expiry usually)
        ('EQUIP-DTHERM',  'HealthPlus Distributors','BN-DTHM-001',  15, 2500.00, -30, None),
        ('EQUIP-POXIM',   'HealthPlus Distributors','BN-POXM-001',  10,12000.00, -20, None),
        ('EQUIP-BPCUFF',  'HealthPlus Distributors','BN-BPCF-001',   5,18000.00, -25, None),

        # Other
        ('OTHER-HSAN500', 'HealthPlus Distributors','BN-HSAN-001', 100, 1200.00, -30, None),
        ('OTHER-SHARP5',  'MedLine Nigeria Ltd',    'BN-SHPC-001',  20, 1800.00, -20, None),
    ]

    created_count = 0
    batch_map = {}

    for (sku, sup_name, batch_no, qty, cost, rec_offset, exp_offset) in batches_data:
        item = items.get(sku)
        supplier = suppliers.get(sup_name)
        if not item or not supplier:
            print(f"  ⚠  Skipping batch {batch_no}: item or supplier not found.")
            continue

        received_date = TODAY + days(rec_offset)
        expiry_date   = (TODAY + days(exp_offset)) if exp_offset is not None else None

        batch, created = StockBatch.objects.get_or_create(
            item=item,
            batch_number=batch_no,
            defaults=dict(
                supplier=supplier,
                quantity_received=qty,
                unit_cost=cost,
                received_date=received_date,
                expiry_date=expiry_date,
                received_by=staff,
            ),
        )
        batch_map[batch_no] = batch

        if created:
            created_count += 1
            # Create the initial RECEIVE movement
            StockMovement.objects.create(
                item=item,
                batch=batch,
                movement_type=StockMovement.TYPE_RECEIVE,
                quantity_delta=qty,
                reference=f"SEED-{batch_no}",
                notes=f"Seed: initial stock for batch {batch_no}",
                performed_by=staff,
            )

    log(f"StockBatches: {created_count} created (with receive movements).")
    return batch_map


# ─────────────────────────────────────────────────────────────────────────────
# 5. Dispense movements  (simulate daily usage)
# ─────────────────────────────────────────────────────────────────────────────

def seed_dispenses(items, batch_map, staff):
    """Simulate dispenses over the last 30 days."""
    from inventory.utils import get_fefo_batch

    dispense_events = [
        # (sku, qty, dept, reference, days_ago)
        ('DRUG-AMOX500',  5,  'Pharmacy',    'VISIT-1001', 28),
        ('DRUG-AMOX500',  3,  'Pharmacy',    'VISIT-1002', 25),
        ('DRUG-PARA500', 10,  'Pharmacy',    'VISIT-1003', 24),
        ('DRUG-ARTS60',   4,  'Emergency',   'VISIT-1004', 20),
        ('DRUG-ARTS60',   2,  'Emergency',   'VISIT-1005', 18),
        ('DRUG-NS1L',    15,  'Ward',        'VISIT-1006', 17),
        ('DRUG-INS10',    3,  'Pharmacy',    'VISIT-1007', 16),
        ('DRUG-METRO200', 6,  'Pharmacy',    'VISIT-1008', 15),
        ('DRUG-PARA500',  8,  'Pharmacy',    'VISIT-1009', 14),
        ('DRUG-NS1L',    20,  'Ward',        'VISIT-1010', 13),
        ('DRUG-AMOX500',  7,  'Pharmacy',    'VISIT-1011', 12),
        ('SUPP-GLOVEL',   5,  'Theatre',     'PROC-2001',  11),
        ('SUPP-GLOVEM',   8,  'OPD',         'PROC-2002',  10),
        ('SUPP-SYR5',     4,  'Ward',        'PROC-2003',   9),
        ('SUPP-FMASK50',  3,  'All',         'PROC-2004',   8),
        ('REAG-MRDTKIT',  6,  'Laboratory',  'LAB-3001',    7),
        ('REAG-BGS50',    4,  'Laboratory',  'LAB-3002',    6),
        ('REAG-HIVDET',   5,  'Laboratory',  'LAB-3003',    5),
        ('SUPP-IVC20',    3,  'Ward',        'PROC-2005',   4),
        ('DRUG-ARTS60',   3,  'Emergency',   'VISIT-1012',  3),
        ('DRUG-PARA500', 12,  'Pharmacy',    'VISIT-1013',  2),
        ('SUPP-GLOVEL',   6,  'All',         'PROC-2006',   1),
        ('REAG-MRDTKIT',  4,  'Laboratory',  'LAB-3004',    1),
        ('OTHER-HSAN500', 5,  'All',         'STORE-001',   1),
        ('DRUG-NS1L',    10,  'Ward',        'VISIT-1014',  0),
        ('SUPP-SYR5',     6,  'Pharmacy',    'PROC-2007',   0),
    ]

    created = 0
    for (sku, qty, dept, ref, days_ago) in dispense_events:
        item = items.get(sku)
        if not item:
            continue
        # Only create if this exact reference doesn't already exist
        if StockMovement.objects.filter(item=item, reference=ref, movement_type=StockMovement.TYPE_DISPENSE).exists():
            continue
        if item.quantity_on_hand < qty:
            print(f"  ⚠  Skipping dispense {ref}: insufficient stock for {sku}.")
            continue
        batch = get_fefo_batch(item)
        m = StockMovement.objects.create(
            item=item,
            batch=batch,
            movement_type=StockMovement.TYPE_DISPENSE,
            quantity_delta=-qty,
            reference=ref,
            department=dept,
            notes=f"Seed dispense for {ref}",
            performed_by=staff,
        )
        # Backdate the created_at timestamp so the dashboard trend graph looks realistic
        StockMovement.objects.filter(pk=m.pk).update(
            created_at=timezone.now() - days(days_ago)
        )
        created += 1

    log(f"Dispense movements: {created} created.")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Adjustments  (a few manual corrections)
# ─────────────────────────────────────────────────────────────────────────────

def seed_adjustments(items, batch_map, staff):
    adjustments = [
        # (sku, movement_type, qty, ref, note)
        ('SUPP-COT500',  StockMovement.TYPE_ADJUST_UP,   5,  'ADJ-001', 'Found extra rolls in back store'),
        ('DRUG-PARA500', StockMovement.TYPE_ADJUST_DOWN, 2,  'ADJ-002', 'Damaged packs removed'),
        ('SUPP-GAUZE',   StockMovement.TYPE_WRITEOFF,    3,  'ADJ-003', 'Opened & contaminated — written off'),
        ('DRUG-ARTS60',  StockMovement.TYPE_RETURN,      2,  'ADJ-004', 'Returned from Emergency — patient discharged'),
        ('SUPP-GLOVEL',  StockMovement.TYPE_TRANSFER,   10,  'ADJ-005', 'Transferred to Theatre store'),
    ]

    created = 0
    for (sku, mv_type, qty, ref, note) in adjustments:
        item = items.get(sku)
        if not item:
            continue
        if StockMovement.objects.filter(item=item, reference=ref).exists():
            continue
        if mv_type in StockMovement.NEGATIVE_TYPES:
            if item.quantity_on_hand < qty:
                print(f"  ⚠  Skipping adjustment {ref}: insufficient stock.")
                continue
            delta = -qty
        else:
            delta = qty
        StockMovement.objects.create(
            item=item,
            movement_type=mv_type,
            quantity_delta=delta,
            reference=ref,
            notes=note,
            performed_by=staff,
        )
        created += 1

    log(f"Adjustment movements: {created} created.")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Purchase Orders
# ─────────────────────────────────────────────────────────────────────────────

def seed_purchase_orders(items, suppliers, staff):
    """Creates POs in various statuses."""

    pos_data = [
        {
            'supplier': 'MedLine Nigeria Ltd',
            'status': PurchaseOrder.STATUS_RECEIVED,
            'ordered_days_ago': 45,
            'expected_days_ago': 38,
            'received_days_ago': 35,
            'lines': [
                {'sku': 'DRUG-AMOX500',  'qty': 120, 'cost': 1500.00},
                {'sku': 'DRUG-METRO200', 'qty':  80, 'cost':  900.00},
                {'sku': 'SUPP-SYR5',     'qty': 150, 'cost': 1800.00},
            ],
        },
        {
            'supplier': 'LabTech International',
            'status': PurchaseOrder.STATUS_RECEIVED,
            'ordered_days_ago': 30,
            'expected_days_ago': 23,
            'received_days_ago': 20,
            'lines': [
                {'sku': 'REAG-MRDTKIT', 'qty': 60,  'cost': 2200.00},
                {'sku': 'REAG-BGS50',   'qty': 50,  'cost': 3500.00},
                {'sku': 'REAG-HAEM5L',  'qty': 15,  'cost':18000.00},
            ],
        },
        {
            'supplier': 'PharmaCare Supplies',
            'status': PurchaseOrder.STATUS_SUBMITTED,
            'ordered_days_ago': 5,
            'expected_days_ago': -7,   # expected in future
            'received_days_ago': None,
            'lines': [
                {'sku': 'DRUG-ARTS60', 'qty': 50,  'cost': 2900.00},
                {'sku': 'DRUG-INS10',  'qty': 30,  'cost': 4600.00},
            ],
        },
        {
            'supplier': 'HealthPlus Distributors',
            'status': PurchaseOrder.STATUS_DRAFT,
            'ordered_days_ago': 1,
            'expected_days_ago': -14,
            'received_days_ago': None,
            'lines': [
                {'sku': 'SUPP-GLOVEL',  'qty': 100, 'cost': 4500.00},
                {'sku': 'SUPP-GLOVEM',  'qty': 100, 'cost': 4500.00},
                {'sku': 'SUPP-FMASK50', 'qty':  80, 'cost': 2500.00},
                {'sku': 'OTHER-HSAN500','qty': 100, 'cost': 1200.00},
            ],
        },
        {
            'supplier': 'MedLine Nigeria Ltd',
            'status': PurchaseOrder.STATUS_CANCELLED,
            'ordered_days_ago': 20,
            'expected_days_ago': 13,
            'received_days_ago': None,
            'lines': [
                {'sku': 'DRUG-NS1L', 'qty': 200, 'cost': 750.00},
            ],
        },
    ]

    created_count = 0
    for po_data in pos_data:
        supplier = suppliers.get(po_data['supplier'])
        if not supplier:
            continue

        ordered_date   = TODAY - days(po_data['ordered_days_ago'])
        expected_date  = TODAY - days(po_data['expected_days_ago'])
        received_date  = (TODAY - days(po_data['received_days_ago'])
                          if po_data['received_days_ago'] is not None else None)

        # Use first line item's SKU as a dedup key (good enough for seeding)
        first_sku = po_data['lines'][0]['sku']
        first_item = items.get(first_sku)
        if not first_item:
            continue

        # Avoid duplicates: check if a PO for this supplier with this status and first item already exists
        if PurchaseOrderLine.objects.filter(
            order__supplier=supplier,
            order__status=po_data['status'],
            item=first_item,
        ).exists():
            continue

        po = PurchaseOrder.objects.create(
            supplier=supplier,
            status=po_data['status'],
            ordered_date=ordered_date,
            expected_delivery=expected_date,
            received_date=received_date,
            raised_by=staff,
            received_by=staff if received_date else None,
            notes=f"Seed PO — {po_data['status']}",
        )

        for line_data in po_data['lines']:
            item = items.get(line_data['sku'])
            if not item:
                continue
            PurchaseOrderLine.objects.get_or_create(
                order=po,
                item=item,
                defaults={
                    'quantity_ordered':  line_data['qty'],
                    'quantity_received': line_data['qty'] if po_data['status'] == PurchaseOrder.STATUS_RECEIVED else 0,
                    'unit_cost':         line_data['cost'],
                }
            )

        created_count += 1

    log(f"Purchase Orders: {created_count} created.")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def run():
    print("\n🏥  Inventory Seed Script Starting …\n")

    staff    = get_or_create_staff()
    suppliers = seed_suppliers()
    items     = seed_items(staff)
    batch_map = seed_batches(items, suppliers, staff)
    seed_dispenses(items, batch_map, staff)
    seed_adjustments(items, batch_map, staff)
    seed_purchase_orders(items, suppliers, staff)

    print("\n✅  Seed complete!\n")
    print("   Superuser credentials: store_admin / Admin1234!")
    print("   Open /inventory/ to see the dashboard.\n")


run()