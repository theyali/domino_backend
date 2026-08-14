from django.urls import path

from .views import (
    InventoryGiftDetailView,
    InventoryGiftListView,
    RestaurantGiftListView,
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
]
