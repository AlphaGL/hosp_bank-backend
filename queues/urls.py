from django.urls import path
from .views import (
    DepartmentQueueListView,
    DepartmentQueueDetailView,
    LiveQueueView,
    QueueSummaryView,
    CallPatientView,
    CompleteQueueEntryView,
    SkipQueueEntryView,
)

app_name = 'queue'

urlpatterns = [
    path('', DepartmentQueueListView.as_view(), name='list'),
    path('live/', LiveQueueView.as_view(), name='live'),
    path('summary/', QueueSummaryView.as_view(), name='summary'),
    path('<int:pk>/', DepartmentQueueDetailView.as_view(), name='detail'),
    path('<int:pk>/call/', CallPatientView.as_view(), name='call'),
    path('<int:pk>/complete/', CompleteQueueEntryView.as_view(), name='complete'),
    path('<int:pk>/skip/', SkipQueueEntryView.as_view(), name='skip'),
]