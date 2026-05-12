"""
Seed script — creates demo staff accounts + services.
Run: python manage.py shell < seed_data.py
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hospital_core.settings')

from patients.models import Staff
from services.models import DiagnosticService

# --- Staff ---
staff_data = [
    dict(username='admin', first_name='System', last_name='Admin', role='admin',
         email='admin@hospital.ng', password='Admin@1234', is_superuser=True, is_staff=True),
    dict(username='reception1', first_name='Amaka', last_name='Obi', role='receptionist',
         email='amaka@hospital.ng', password='Pass@1234', department='Front Desk'),
    dict(username='finance1', first_name='Emeka', last_name='Nwosu', role='finance',
         email='emeka@hospital.ng', password='Pass@1234', department='Finance'),
    dict(username='doctor_xray', first_name='Dr. Bola', last_name='Adeyemi', role='doctor',
         email='bola@hospital.ng', password='Pass@1234', department='Radiology'),
    dict(username='doctor_us', first_name='Dr. Kemi', last_name='Suleiman', role='doctor',
         email='kemi@hospital.ng', password='Pass@1234', department='Ultrasound'),
    dict(username='doctor_mammo', first_name='Dr. Ngozi', last_name='Eze', role='doctor',
         email='ngozi@hospital.ng', password='Pass@1234', department='Mammography'),
]

for d in staff_data:
    password = d.pop('password')
    if not Staff.objects.filter(username=d['username']).exists():
        u = Staff(**d)
        u.set_password(password)
        u.save()
        print(f"  Created staff: {u.username}")
    else:
        print(f"  Skipped (exists): {d['username']}")

# --- Diagnostic Services ---
services = [
    dict(name='Chest X-Ray', code='XRAY-CHEST', category='imaging', department='Radiology',
         base_price=8500, duration_minutes=20, description='Standard chest radiograph'),
    dict(name='Abdominal X-Ray', code='XRAY-ABD', category='imaging', department='Radiology',
         base_price=9000, duration_minutes=20, description='Abdominal plain film'),
    dict(name='Skull X-Ray', code='XRAY-SKULL', category='imaging', department='Radiology',
         base_price=9500, duration_minutes=25, description='Skull series'),
    dict(name='Abdominal Ultrasound', code='US-ABD', category='imaging', department='Ultrasound',
         base_price=15000, duration_minutes=30, description='Full abdominal scan'),
    dict(name='Pelvic Ultrasound', code='US-PELV', category='imaging', department='Ultrasound',
         base_price=15000, duration_minutes=30, description='Pelvic organ evaluation'),
    dict(name='Obstetric Ultrasound', code='US-OBS', category='imaging', department='Ultrasound',
         base_price=18000, duration_minutes=45, description='Pregnancy scan'),
    dict(name='Breast Ultrasound', code='US-BREAST', category='imaging', department='Ultrasound',
         base_price=16000, duration_minutes=30, description='Breast tissue scan'),
    dict(name='Screening Mammography', code='MAMMO-SCR', category='imaging', department='Mammography',
         base_price=25000, duration_minutes=30, description='Routine breast cancer screening'),
    dict(name='Diagnostic Mammography', code='MAMMO-DX', category='imaging', department='Mammography',
         base_price=30000, duration_minutes=45, description='Diagnostic mammography with views'),
    dict(name='Doppler Ultrasound', code='US-DOPPLER', category='imaging', department='Ultrasound',
         base_price=22000, duration_minutes=40, description='Blood flow evaluation'),
]

for s in services:
    obj, created = DiagnosticService.objects.get_or_create(code=s['code'], defaults=s)
    print(f"  {'Created' if created else 'Exists'} service: {obj.name}")

print("\n✅ Seed complete.")
print("\nDemo Credentials:")
print("  Admin      → admin / Admin@1234")
print("  Reception  → reception1 / Pass@1234")
print("  Finance    → finance1 / Pass@1234")
print("  Radiology  → doctor_xray / Pass@1234")
print("  Ultrasound → doctor_us / Pass@1234")
print("  Mammography→ doctor_mammo / Pass@1234")
