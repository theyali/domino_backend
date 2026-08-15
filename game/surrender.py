from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.ranking import record_match_statistics
from rooms.models import GameRoom, RoomPlayer
from rooms.realtime import broadcast_game_state_updated

from .models import GameSession
from .turn_clock import clear_turn_clock


@transaction.atomic
def surrender_game(*, room_id, player_id):
    session = (
        GameSession.objects.select_for_update()
        .select_related("room", "current_player", "opening_player")
        .prefetch_related("room__players")
        .get(room_id=room_id)
    )

    if session.status != GameSession.Status.ACTIVE:
        raise ValidationError({"game": "Сдаться можно только во время активного матча."})

    room = session.room
    players = list(room.players.filter(is_active=True))
    surrendering_player = next(
        (player for player in players if player.pk == player_id),
        None,
    )

    if surrendering_player is None:
        raise ValidationError({"player_id": "Игрок не найден в этой комнате."})

    winner_ids = [player.pk for player in players if player.pk != player_id]
    if not winner_ids:
        raise ValidationError({"game": "Некому засчитать победу после сдачи."})

    hands = {key: list(value) for key, value in (session.hands or {}).items()}
    scores = {str(key): int(value) for key, value in (session.scores or {}).items()}
    hand_points = {
        player.pk: _hand_points(hands.get(str(player.pk), []))
        for player in players
    }

    session.status = GameSession.Status.FINISHED
    session.last_round_result = {
        "reason": "surrender",
        "winner_player_ids": winner_ids,
        "hand_points": {str(key): value for key, value in hand_points.items()},
        "added_penalties": {str(player.pk): 0 for player in players},
        "added_points": {str(player.pk): 0 for player in players},
        "total_scores": scores,
        "match_loser_player_ids": [player_id],
        "match_winner_player_ids": winner_ids,
        "surrendered_player_id": player_id,
    }
    clear_turn_clock(session)
    session.version += 1
    session.save(
        update_fields=[
            "status",
            "last_round_result",
            "turn_started_at",
            "turn_deadline_at",
            "version",
            "updated_at",
        ]
    )

    record_match_statistics(
        session=session,
        players=players,
        winner_player_ids=winner_ids,
        loser_player_ids=[player_id],
    )

    room.status = GameRoom.Status.FINISHED
    room.save(update_fields=["status"])

    transaction.on_commit(lambda: broadcast_game_state_updated(room.pk))
    return session


def _hand_points(hand):
    return sum(item["left"] + item["right"] for item in hand)
