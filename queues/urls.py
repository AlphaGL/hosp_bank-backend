from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentQueueViewSet

router = DefaultRouter()
router.register('', DepartmentQueueViewSet, basename='queue')
urlpatterns = [path('', include(router.urls))]
