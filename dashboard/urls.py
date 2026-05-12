from django.urls import path
from .views import DashboardSummaryView, DepartmentWorkloadView

urlpatterns = [
    path('summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('workload/', DepartmentWorkloadView.as_view(), name='department-workload'),
]
