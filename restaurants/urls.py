from django.urls import path

from .views import RestaurantDetailView, RestaurantListView

urlpatterns = [
    path("restaurants/", RestaurantListView.as_view(), name="restaurant-list"),
    path(
        "restaurants/<int:pk>/",
        RestaurantDetailView.as_view(),
        name="restaurant-detail",
    ),
]
