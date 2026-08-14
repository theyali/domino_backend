from django.urls import path

from .views import JoinRoomView, LeaveRoomView, RestaurantRoomsView, RoomDetailView

urlpatterns = [
    path(
        "restaurants/<int:restaurant_id>/rooms/",
        RestaurantRoomsView.as_view(),
        name="restaurant-rooms",
    ),
    path("rooms/<int:room_id>/", RoomDetailView.as_view(), name="room-detail"),
    path("rooms/<int:room_id>/join/", JoinRoomView.as_view(), name="room-join"),
    path("rooms/<int:room_id>/leave/", LeaveRoomView.as_view(), name="room-leave"),
]
