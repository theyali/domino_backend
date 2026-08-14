from django.urls import path

from .views import (
    DrawDominoView,
    GameStateView,
    NextRoundView,
    PassTurnView,
    PlayDominoView,
    StartGameView,
)

urlpatterns = [
    path("rooms/<int:room_id>/start/", StartGameView.as_view(), name="game-start"),
    path("rooms/<int:room_id>/game/", GameStateView.as_view(), name="game-state"),
    path(
        "rooms/<int:room_id>/game/next-round/",
        NextRoundView.as_view(),
        name="game-next-round",
    ),
    path(
        "rooms/<int:room_id>/game/play/",
        PlayDominoView.as_view(),
        name="game-play-domino",
    ),
    path(
        "rooms/<int:room_id>/game/draw/",
        DrawDominoView.as_view(),
        name="game-draw-domino",
    ),
    path(
        "rooms/<int:room_id>/game/pass/",
        PassTurnView.as_view(),
        name="game-pass-turn",
    ),
]
