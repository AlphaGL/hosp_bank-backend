from django.urls import path
from .views import (
    NotificationListView,
    NotificationDetailView,
    UnreadNotificationsView,
    MarkNotificationReadView,
    MarkAllReadView,
)

app_name = 'notifications'

urlpatterns = [
    path('', NotificationListView.as_view(), name='list'),
    path('<int:pk>/', NotificationDetailView.as_view(), name='detail'),
    path('unread/', UnreadNotificationsView.as_view(), name='unread'),
    path('<int:pk>/mark-read/', MarkNotificationReadView.as_view(), name='mark-read'),
    path('mark-all-read/', MarkAllReadView.as_view(), name='mark-all-read'),
]