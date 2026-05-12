from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PatientViewSet, VisitViewSet, StaffViewSet

router = DefaultRouter()
router.register('records', PatientViewSet, basename='patient')
router.register('visits', VisitViewSet, basename='visit')
router.register('staff', StaffViewSet, basename='staff')

urlpatterns = [
    path('', include(router.urls)),
]
