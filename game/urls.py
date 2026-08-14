from django.urls import path

from .views import GameStateView, PlayDominoView, StartGameView

urlpatterns = [
    path("rooms/<int:room_id>/start/", StartGameView.as_view(), name="game-start"),
    path("rooms/<int:room_id>/game/", GameStateView.as_view(), name="game-state"),
    path(
        "rooms/<int:room_id>/game/play/",
        PlayDominoView.as_view(),
        name="game-play-domino",
    ),
]
