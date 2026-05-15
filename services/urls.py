from django.urls import path
from .views import (
    # Catalogue
    DiagnosticServiceListView,
    DiagnosticServiceDetailView,
    DiagnosticServiceCreateView,
    DiagnosticServiceUpdateView,
    DiagnosticServiceDeleteView,
    ServicesByDepartmentView,
    # Visit services
    VisitServiceListView,
    VisitServiceDetailView,
    VisitServiceCreateView,
    VisitServiceUpdateView,
    UpdateVisitServiceStatusView,
    UploadReportView,
)

app_name = 'services'

urlpatterns = [
    # ── Catalogue ──────────────────────────────────────────────────────────
    path('catalogue/', DiagnosticServiceListView.as_view(), name='catalogue-list'),
    path('catalogue/create/', DiagnosticServiceCreateView.as_view(), name='catalogue-create'),
    path('catalogue/by-department/', ServicesByDepartmentView.as_view(), name='by-department'),
    path('catalogue/<int:pk>/', DiagnosticServiceDetailView.as_view(), name='catalogue-detail'),
    path('catalogue/<int:pk>/edit/', DiagnosticServiceUpdateView.as_view(), name='catalogue-edit'),
    path('catalogue/<int:pk>/delete/', DiagnosticServiceDeleteView.as_view(), name='catalogue-delete'),

    # ── Visit services ─────────────────────────────────────────────────────
    path('visit-services/', VisitServiceListView.as_view(), name='visit-service-list'),
    path('visit-services/create/', VisitServiceCreateView.as_view(), name='visit-service-create'),
    path('visit-services/<int:pk>/', VisitServiceDetailView.as_view(), name='visit-service-detail'),
    path('visit-services/<int:pk>/edit/', VisitServiceUpdateView.as_view(), name='visit-service-edit'),
    path('visit-services/<int:pk>/update-status/', UpdateVisitServiceStatusView.as_view(), name='update-status'),
    path('visit-services/<int:pk>/upload-report/', UploadReportView.as_view(), name='upload-report'),
]