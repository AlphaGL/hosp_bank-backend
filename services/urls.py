from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DiagnosticServiceViewSet, VisitServiceViewSet

router = DefaultRouter()
router.register('catalogue', DiagnosticServiceViewSet, basename='service')
router.register('visit-services', VisitServiceViewSet, basename='visit-service')

urlpatterns = [path('', include(router.urls))]
