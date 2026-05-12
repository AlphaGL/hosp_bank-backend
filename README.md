# 🏥 Diagnostic & Patient Workflow — Django Backend

A production-ready REST API backend for managing hospital diagnostic services
(X-ray, Ultrasound, Mammography). Built with Django + DRF + JWT.

---

## ⚡ Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run with SQLite (default — zero config)
python manage.py migrate
python manage.py shell < seed_data.py   # Creates demo accounts + services
python manage.py runserver
```

### To use PostgreSQL instead:
```bash
export USE_POSTGRES=true
export DB_NAME=hospital_db
export DB_USER=hospital_user
export DB_PASSWORD=yourpassword
export DB_HOST=localhost
python manage.py migrate
```

---

## 🔐 Demo Credentials

| Role          | Username      | Password    |
|--------------|---------------|-------------|
| Admin         | admin         | Admin@1234  |
| Receptionist  | reception1    | Pass@1234   |
| Finance       | finance1      | Pass@1234   |
| Radiologist   | doctor_xray   | Pass@1234   |
| Sonographer   | doctor_us     | Pass@1234   |
| Mammographer  | doctor_mammo  | Pass@1234   |

---

## 📡 API Endpoints

### Authentication
| Method | Endpoint                  | Description          |
|--------|---------------------------|----------------------|
| POST   | /api/auth/login/          | Get JWT tokens       |
| POST   | /api/auth/logout/         | Blacklist token      |
| POST   | /api/auth/refresh/        | Refresh access token |
| GET    | /api/auth/me/             | Current user profile |

### Patients
| Method | Endpoint                            | Description               |
|--------|-------------------------------------|---------------------------|
| GET    | /api/patients/records/              | List all patients         |
| POST   | /api/patients/records/              | Register new patient      |
| GET    | /api/patients/records/{id}/         | Patient detail            |
| GET    | /api/patients/records/{id}/visits/  | Patient visit history     |
| GET    | /api/patients/records/search/?q=    | Search by name/ID/phone   |
| GET    | /api/patients/visits/               | All visits                |
| POST   | /api/patients/visits/               | Create visit              |
| PATCH  | /api/patients/visits/{id}/update-status/ | Change visit status  |
| GET    | /api/patients/staff/                | Staff list (admin only)   |
| POST   | /api/patients/staff/                | Create staff (admin only) |

### Services
| Method | Endpoint                                    | Description            |
|--------|---------------------------------------------|------------------------|
| GET    | /api/services/catalogue/                    | All diagnostic services|
| GET    | /api/services/catalogue/by-department/?dept=| Filter by dept         |
| GET    | /api/services/visit-services/               | Visit service records  |
| POST   | /api/services/visit-services/               | Add service to visit   |
| PATCH  | /api/services/visit-services/{id}/update-status/ | Update service status |
| POST   | /api/services/visit-services/{id}/upload-report/| Upload report/image  |

### Billing
| Method | Endpoint                          | Description              |
|--------|-----------------------------------|--------------------------|
| GET    | /api/billing/payments/            | All payments             |
| POST   | /api/billing/payments/            | Create payment record    |
| GET    | /api/billing/payments/{id}/       | Payment detail           |
| POST   | /api/billing/payments/{id}/confirm/| Confirm payment         |
| GET    | /api/billing/payments/{id}/receipt/| Generate receipt        |

### Queue Management
| Method | Endpoint                          | Description                  |
|--------|-----------------------------------|------------------------------|
| GET    | /api/queues/                      | All queue entries (today)    |
| GET    | /api/queues/live/                 | Live waiting queue           |
| GET    | /api/queues/summary/              | Dept-wise counts             |
| PATCH  | /api/queues/{id}/call/            | Call patient (→ In Progress) |
| PATCH  | /api/queues/{id}/complete/        | Mark completed               |
| PATCH  | /api/queues/{id}/skip/            | Skip patient                 |

### Notifications
| Method | Endpoint                             | Description         |
|--------|--------------------------------------|---------------------|
| GET    | /api/notifications/                  | All notifications   |
| GET    | /api/notifications/unread/           | Unread count + list |
| PATCH  | /api/notifications/{id}/mark-read/   | Mark one read       |
| POST   | /api/notifications/mark-all-read/    | Mark all read       |

### Dashboard (Admin)
| Method | Endpoint                    | Description           |
|--------|-----------------------------|-----------------------|
| GET    | /api/dashboard/summary/     | Full KPI summary      |
| GET    | /api/dashboard/workload/    | Dept workload today   |

---

## 🔄 Patient Flow (How It Works)

```
1. POST /api/patients/records/         → Register patient (Receptionist)
2. POST /api/patients/visits/          → Create visit with priority
3. POST /api/services/visit-services/  → Add services (X-ray, Ultrasound...)
4. POST /api/billing/payments/         → Create payment record (Finance)
5. POST /api/billing/payments/{id}/confirm/ → Confirm payment
       ↳ Auto: visit status → paid
       ↳ Auto: queue entries created per department
       ↳ Auto: front desk notified
6. GET  /api/queues/live/?department=Radiology → Doctor sees queue
7. PATCH /api/queues/{id}/call/        → Doctor calls patient
8. PATCH /api/services/visit-services/{id}/update-status/ → status=completed
       ↳ Auto: if all services done → visit marked completed
       ↳ Auto: front desk notified
```

---

## 🏗️ Project Structure

```
hospital_core/        ← Django project config
├── settings.py       ← SQLite default, env-switch to PostgreSQL
└── urls.py           ← Root URL routing

patients/             ← Staff auth + Patient + Visit models
services/             ← DiagnosticService + VisitService
billing/              ← Payment + receipt logic
queues/               ← DepartmentQueue with priority support
notifications/        ← Role-targeted event notifications
dashboard/            ← Admin analytics views

seed_data.py          ← Demo data (staff + services)
requirements.txt
```

---

## 🔒 Role-Based Access

| Action                  | Receptionist | Finance | Doctor | Admin |
|-------------------------|:---:|:---:|:---:|:---:|
| Register patients       | ✅  | —   | —   | ✅  |
| Create visits           | ✅  | —   | —   | ✅  |
| View patients           | ✅  | ✅  | ✅  | ✅  |
| Confirm payments        | —   | ✅  | —   | ✅  |
| View queue              | ✅  | —   | ✅  | ✅  |
| Update service status   | —   | —   | ✅  | ✅  |
| Upload reports          | —   | —   | ✅  | ✅  |
| Manage staff            | —   | —   | —   | ✅  |
| View dashboard          | —   | —   | —   | ✅  |

---

## 🚀 Production Deployment

```bash
# Environment variables to set
SECRET_KEY=your-very-secret-key-here
DEBUG=false
USE_POSTGRES=true
DB_NAME=hospital_db
DB_USER=hospital_user
DB_PASSWORD=strongpassword
DB_HOST=localhost

# Collect static files
python manage.py collectstatic

# Run with Gunicorn
gunicorn hospital_core.wsgi:application --bind 0.0.0.0:8000 --workers 4
```
