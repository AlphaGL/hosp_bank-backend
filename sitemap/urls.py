from django.urls import path
from .views import NavigationHubView, PlatformStatsView, ActivityLogView

app_name = 'sitemap'

urlpatterns = [
    path('hub/',          NavigationHubView.as_view(),  name='hub'),
    path('stats/',        PlatformStatsView.as_view(),  name='stats'),
    path('activity-log/', ActivityLogView.as_view(),    name='activity_log'),
]