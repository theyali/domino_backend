from django.urls import path

from .views import (
    GiftPurchaseSummaryView,
    InventoryGiftDetailView,
    InventoryGiftListView,
    PurchaseGiftView,
    RestaurantGiftListView,
    SendRoomGiftView,
)


urlpatterns = [
    path(
        "restaurants/<int:restaurant_id>/gifts/",
        RestaurantGiftListView.as_view(),
        name="restaurant-gifts",
    ),
    path(
        "restaurants/<int:restaurant_id>/gifts/<int:gift_id>/purchase/",
        PurchaseGiftView.as_view(),
        name="purchase-gift",
    ),
    path(
        "gifts/purchases/",
        GiftPurchaseSummaryView.as_view(),
        name="gift-purchases",
    ),
    path(
        "inventory/gifts/",
        InventoryGiftListView.as_view(),
        name="inventory-gifts",
    ),
    path(
        "inventory/gifts/<int:pk>/",
        InventoryGiftDetailView.as_view(),
        name="inventory-gift-detail",
    ),
    path(
        "rooms/<int:room_id>/gifts/send/",
        SendRoomGiftView.as_view(),
        name="send-room-gift",
    ),
]
