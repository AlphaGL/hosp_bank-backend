from django.urls import path
from .views import (
    PaymentListView,
    PaymentDetailView,
    PaymentConfirmView,
    PaymentReceiptView,
    DiscountRequestView,
    DiscountRequestListView,
    DiscountReviewView,
)

app_name = 'payments'

urlpatterns = [
    # Unified billing hub (list + inline create)
    path('',                          PaymentListView.as_view(),         name='list'),

    # Detail, confirm, receipt
    path('<int:pk>/',                  PaymentDetailView.as_view(),       name='detail'),
    path('<int:pk>/confirm/',          PaymentConfirmView.as_view(),      name='confirm'),
    path('<int:pk>/receipt/',          PaymentReceiptView.as_view(),      name='receipt'),

    # Discount flow
    path('<int:pk>/request-discount/', DiscountRequestView.as_view(),     name='request-discount'),
    path('discounts/',                 DiscountRequestListView.as_view(), name='discounts'),
    path('discounts/<int:pk>/review/', DiscountReviewView.as_view(),      name='discount-review'),
]