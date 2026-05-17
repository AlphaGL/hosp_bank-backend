from django.urls import path
from .views import (
    # Dashboard & stats
    InventoryDashboardView,
    InventoryStatsView,
    LowStockAlertView,

    # Consumable Items
    ConsumableItemListView,
    ConsumableItemDetailView,
    ConsumableItemCreateView,
    ConsumableItemUpdateView,
    ConsumableItemDeactivateView,

    # Suppliers
    SupplierListView,
    SupplierDetailView,
    SupplierCreateView,
    SupplierUpdateView,

    # Stock Batches
    StockBatchListView,
    StockBatchCreateView,

    # Stock Movements (ledger)
    StockMovementListView,
    StockMovementDetailView,

    # Dispense & Adjust
    StockDispenseView,
    StockAdjustmentView,

    # Purchase Orders
    PurchaseOrderListView,
    PurchaseOrderDetailView,
    PurchaseOrderCreateView,
    PurchaseOrderUpdateView,
    PurchaseOrderSubmitView,
    PurchaseOrderReceiveView,
    PurchaseOrderCancelView,
)

app_name = 'inventory'

urlpatterns = [

    # ── Dashboard & reports ────────────────────────────────────────────────
    path('',          InventoryDashboardView.as_view(), name='dashboard'),
    path('stats/',    InventoryStatsView.as_view(),     name='stats'),
    path('alerts/',   LowStockAlertView.as_view(),      name='alerts'),

    # ── Consumable Items ───────────────────────────────────────────────────
    path('items/',                         ConsumableItemListView.as_view(),       name='item-list'),
    path('items/new/',                     ConsumableItemCreateView.as_view(),     name='item-create'),
    path('items/<int:pk>/',                ConsumableItemDetailView.as_view(),     name='item-detail'),
    path('items/<int:pk>/edit/',           ConsumableItemUpdateView.as_view(),     name='item-edit'),
    path('items/<int:pk>/deactivate/',     ConsumableItemDeactivateView.as_view(), name='item-deactivate'),

    # ── Suppliers ──────────────────────────────────────────────────────────
    path('suppliers/',                 SupplierListView.as_view(),   name='supplier-list'),
    path('suppliers/new/',             SupplierCreateView.as_view(), name='supplier-create'),
    path('suppliers/<int:pk>/',        SupplierDetailView.as_view(), name='supplier-detail'),
    path('suppliers/<int:pk>/edit/',   SupplierUpdateView.as_view(), name='supplier-edit'),

    # ── Stock Batches ──────────────────────────────────────────────────────
    path('batches/',       StockBatchListView.as_view(),   name='batch-list'),
    path('batches/new/',   StockBatchCreateView.as_view(), name='batch-create'),

    # ── Stock Movements (ledger — read-only list + detail) ─────────────────
    path('movements/',           StockMovementListView.as_view(),   name='movement-list'),
    path('movements/<int:pk>/',  StockMovementDetailView.as_view(), name='movement-detail'),

    # ── Dispense & Adjustments ─────────────────────────────────────────────
    path('dispense/',    StockDispenseView.as_view(),    name='dispense'),
    path('adjust/',      StockAdjustmentView.as_view(),  name='adjust'),

    # ── Purchase Orders ────────────────────────────────────────────────────
    path('purchase-orders/',                    PurchaseOrderListView.as_view(),    name='po-list'),
    path('purchase-orders/new/',                PurchaseOrderCreateView.as_view(),  name='po-create'),
    path('purchase-orders/<int:pk>/',           PurchaseOrderDetailView.as_view(),  name='po-detail'),
    path('purchase-orders/<int:pk>/edit/',      PurchaseOrderUpdateView.as_view(),  name='po-edit'),
    path('purchase-orders/<int:pk>/submit/',    PurchaseOrderSubmitView.as_view(),  name='po-submit'),
    path('purchase-orders/<int:pk>/receive/',   PurchaseOrderReceiveView.as_view(), name='po-receive'),
    path('purchase-orders/<int:pk>/cancel/',    PurchaseOrderCancelView.as_view(),  name='po-cancel'),
]