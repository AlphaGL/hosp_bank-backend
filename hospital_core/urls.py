from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Patients app: auth, staff, patients, visits ───────────────────────
    # app_name = 'patients'  →  namespace 'patients'
    path('', include('patients.urls', namespace='patients')),

    # ── Payments ──────────────────────────────────────────────────────────
    # app_name = 'payments'  →  namespace 'payments'
    path('payments/', include('billing.urls', namespace='payments')),

    # ── Services / catalogue ──────────────────────────────────────────────
    # app_name = 'services'  →  namespace 'services'
    path('services/', include('services.urls', namespace='services')),

    # ── Queue ─────────────────────────────────────────────────────────────
    # app_name = 'queue'  →  namespace 'queue'
    path('queue/', include('queues.urls', namespace='queue')),

    # ── Notifications ─────────────────────────────────────────────────────
    # app_name = 'notifications'  →  namespace 'notifications'
    path('notifications/', include('notifications.urls', namespace='notifications')),

    # ── Dashboard (no namespace — uses plain names 'dashboard-summary' etc) ─
    path('dashboard/', include('dashboard.urls')),

    path('inventory/', include('inventory.urls', namespace='inventory')),

    path('nav/', include('sitemap.urls')),   # add this
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)