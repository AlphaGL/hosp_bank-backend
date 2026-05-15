from django.urls import path
from .views import (
    PaymentListView,
    PaymentDetailView,
    PaymentCreateView,
    PaymentConfirmView,
    PaymentReceiptView,
)

app_name = 'payments'

urlpatterns = [
    # List & create
    path('',           PaymentListView.as_view(),    name='list'),
    path('new/',       PaymentCreateView.as_view(),  name='create'),

    # Detail, confirm, receipt
    path('<int:pk>/',             PaymentDetailView.as_view(), name='detail'),
    path('<int:pk>/confirm/',     PaymentConfirmView.as_view(), name='confirm'),
    path('<int:pk>/receipt/',     PaymentReceiptView.as_view(), name='receipt'),
]