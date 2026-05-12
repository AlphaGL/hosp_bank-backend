from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework_simplejwt.views import TokenRefreshView
from patients.auth_views import LoginView, LogoutView, StaffProfileView

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Auth endpoints ────────────────────────────────────────────────────────
    path('api/auth/login/',   LoginView.as_view(),        name='login'),
    path('api/auth/logout/',  LogoutView.as_view(),       name='logout'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('api/auth/me/',      StaffProfileView.as_view(), name='staff-profile'),

    # ── Core API modules ──────────────────────────────────────────────────────
    path('api/patients/',      include('patients.urls')),
    path('api/services/',      include('services.urls')),
    path('api/billing/',       include('billing.urls')),
    path('api/queues/',        include('queues.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/dashboard/',     include('dashboard.urls')),

    # ── Frontend template views ───────────────────────────────────────────────
    # Fixed: these were missing — hitting / gave a 404 even though the HTML
    # templates existed.  TemplateView serves them without a custom view class.
    path('login/', TemplateView.as_view(template_name='login.html'),        name='login-page'),
    path('patients/records/', TemplateView.as_view(template_name='patient_list.html'), name='patient-list'),
    # Catch-all: serve the SPA shell for every other non-API path so the
    # frontend router (window.location.href redirects) works correctly.
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)