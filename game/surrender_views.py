from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PlayerGameActionSerializer
from .services import game_state_for_player
from .surrender import surrender_game


class SurrenderGameView(APIView):
    def post(self, request, room_id):
        serializer = PlayerGameActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        player_id = serializer.validated_data["player_id"]

        session = surrender_game(room_id=room_id, player_id=player_id)

        return Response(
            {
                "type": "game_state",
                "game": game_state_for_player(
                    session=session,
                    player_id=player_id,
                ),
            }
        )
