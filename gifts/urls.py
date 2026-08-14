from django.urls import path

from .views import (
    InventoryGiftDetailView,
    InventoryGiftListView,
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
