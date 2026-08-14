from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from rooms.models import GameRoom, RoomPlayer

from .models import GameSession
from .serializers import (
    PlayDominoSerializer,
    PlayerGameActionSerializer,
    StartGameSerializer,
)
from .services import (
    draw_domino,
    game_state_for_player,
    pass_turn,
    play_domino,
    start_game,
    start_next_round,
)


class StartGameView(APIView):
    def post(self, request, room_id):
        serializer = StartGameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        player_id = serializer.validated_data["player_id"]

        session = start_game(room_id=room_id, player_id=player_id)
        session = _game_session_queryset().get(pk=session.pk)

        return Response(
            {
                "type": "game_started",
                "game": game_state_for_player(
                    session=session,
                    player_id=player_id,
                ),
            }
        )


class NextRoundView(APIView):
    def post(self, request, room_id):
        serializer = PlayerGameActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        player_id = serializer.validated_data["player_id"]

        session = start_next_round(room_id=room_id, player_id=player_id)
        session = _game_session_queryset().get(pk=session.pk)

        return Response(
            {
                "type": "game_state",
                "game": game_state_for_player(
                    session=session,
                    player_id=player_id,
                ),
            }
        )


class GameStateView(APIView):
    def get(self, request, room_id):
        room = get_object_or_404(GameRoom, pk=room_id)

        try:
            player_id = int(request.query_params.get("player_id", ""))
        except (TypeError, ValueError):
            return Response(
                {"player_id": ["Передайте корректный player_id."]},
                status=400,
            )

        if not RoomPlayer.objects.filter(
            pk=player_id,
            room=room,
            is_active=True,
        ).exists():
            return Response(
                {"player_id": ["Игрок не найден в этой комнате."]},
                status=403,
            )

        session = get_object_or_404(_game_session_queryset(), room=room)

        return Response(
            {
                "type": "game_state",
                "game": game_state_for_player(
                    session=session,
                    player_id=player_id,
                ),
            }
        )


class PlayDominoView(APIView):
    def post(self, request, room_id):
        serializer = PlayDominoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        player_id = serializer.validated_data["player_id"]
        session = play_domino(
            room_id=room_id,
            player_id=player_id,
            domino_id=serializer.validated_data["domino_id"],
            side=serializer.validated_data["side"],
        )
        session = _game_session_queryset().get(pk=session.pk)

        return Response(
            {
                "type": "game_state",
                "game": game_state_for_player(
                    session=session,
                    player_id=player_id,
                ),
            }
        )


class DrawDominoView(APIView):
    def post(self, request, room_id):
        serializer = PlayerGameActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        player_id = serializer.validated_data["player_id"]

        session = draw_domino(room_id=room_id, player_id=player_id)
        session = _game_session_queryset().get(pk=session.pk)

        return Response(
            {
                "type": "game_state",
                "game": game_state_for_player(
                    session=session,
                    player_id=player_id,
                ),
            }
        )


class PassTurnView(APIView):
    def post(self, request, room_id):
        serializer = PlayerGameActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        player_id = serializer.validated_data["player_id"]

        session = pass_turn(room_id=room_id, player_id=player_id)
        session = _game_session_queryset().get(pk=session.pk)

        return Response(
            {
                "type": "game_state",
                "game": game_state_for_player(
                    session=session,
                    player_id=player_id,
                ),
            }
        )


def _game_session_queryset():
    return (
        GameSession.objects.select_related(
            "room",
            "current_player",
            "opening_player",
        )
        .prefetch_related("room__players")
    )
