from django.urls import path
from .views import (
    # Auth
    StaffLoginView, StaffLogoutView, StaffProfileView,
    # Dashboard
    DashboardView,
    # Staff
    StaffListView, StaffCreateView, StaffUpdateView,
    # Patient
    PatientListView, PatientDetailView, PatientCreateView, PatientUpdateView,
    # Visit
    VisitListView, VisitDetailView, VisitCreateView, VisitUpdateStatusView,
)

app_name = 'patients'

urlpatterns = [
    # Auth
    path('login/',   StaffLoginView.as_view(),  name='login'),
    path('logout/',  StaffLogoutView.as_view(), name='logout'),
    path('profile/', StaffProfileView.as_view(), name='profile'),

    # Dashboard
    path('', DashboardView.as_view(), name='dashboard'),

    # Staff (admin only)
    path('staff/',          StaffListView.as_view(),         name='staff-list'),
    path('staff/new/',      StaffCreateView.as_view(),       name='staff-create'),
    path('staff/<int:pk>/edit/', StaffUpdateView.as_view(),  name='staff-update'),

    # Patients
    path('records/',              PatientListView.as_view(),   name='patient-list'),
    path('records/new/',          PatientCreateView.as_view(), name='patient-create'),
    path('records/<int:pk>/',     PatientDetailView.as_view(), name='patient-detail'),
    path('records/<int:pk>/edit/', PatientUpdateView.as_view(), name='patient-update'),

    # Visits
    path('visits/',                       VisitListView.as_view(),         name='visit-list'),
    path('visits/new/',                   VisitCreateView.as_view(),       name='visit-create'),
    path('visits/<int:pk>/',              VisitDetailView.as_view(),       name='visit-detail'),
    path('visits/<int:pk>/update-status/', VisitUpdateStatusView.as_view(), name='visit-update-status'),
]