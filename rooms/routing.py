from django.urls import re_path

from .consumers import RoomLobbyConsumer


websocket_urlpatterns = [
    re_path(
        r"^ws/rooms/(?P<room_id>\d+)/$",
        RoomLobbyConsumer.as_asgi(),
    ),
]
