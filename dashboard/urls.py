from django.urls import path
from .views import DashboardSummaryView, DepartmentWorkloadView

# No app_name namespace — keeps existing {% url 'dashboard-summary' %}
# and {% url 'department-workload' %} references in templates working as-is.
urlpatterns = [
    path('summary/',  DashboardSummaryView.as_view(),   name='dashboard-summary'),
    path('workload/', DepartmentWorkloadView.as_view(), name='department-workload'),
]