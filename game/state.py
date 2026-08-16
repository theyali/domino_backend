from django.utils import timezone

from rooms.models import GameRoom

from .engine import phone_open_end_sum, phone_open_ends
from .models import GameSession


def _serialize_active_gift(player):
    gift = player.active_gift
    if gift is None:
        return None

    return {
        "id": gift.id,
        "restaurant_id": gift.restaurant_id,
        "is_global": gift.is_global,
        "name": gift.name,
        "level": gift.level,
        "image_url": gift.image.url if gift.image else None,
    }


def _avatar_url_for_player(player):
    user = player.user
    if user is None:
        return None

    profile = getattr(user, "profile", None)
    if profile is None or not profile.avatar:
        return None
    return profile.avatar.url


def _gender_for_player(player):
    user = player.user
    if user is None:
        return ""
    profile = getattr(user, "profile", None)
    return profile.gender if profile is not None else ""


def _dominoes_with_mode(dominoes, game_mode):
    return [
        {**domino, "game_mode": game_mode}
        for domino in dominoes
    ]


def serialize_game_state_for_player(session, player_id):
    room = session.room
    players = list(room.players.all())
    hands = session.hands or {}
    scores = session.scores or {}
    my_hand = hands.get(str(player_id), [])
    table = session.table or []
    is_phone = room.game_mode == GameRoom.GameMode.PHONE

    phone_ends = phone_open_ends(table) if is_phone and table else {}

    # Во время активной партии чужие руки являются закрытой информацией.
    # После завершения раунда/матча раскрываем финальный snapshot, чтобы клиент
    # мог наглядно показать, какие костяшки остались у каждого игрока.
    revealed_hands = {}
    if session.status != GameSession.Status.ACTIVE:
        revealed_hands = {
            str(player.id): _dominoes_with_mode(
                hands.get(str(player.id), []),
                room.game_mode,
            )
            for player in players
        }

    return {
        "game_id": session.pk,
        "room_id": room.pk,
        "game_mode": room.game_mode,
        "game_mode_label": room.game_mode_label,
        "target_score": room.target_score,
        "status": session.status,
        "round_number": session.round_number,
        "version": session.version,
        "server_time": timezone.now().isoformat(),
        "current_player_id": session.current_player_id,
        "opening_player_id": session.opening_player_id,
        "opening_domino_id": session.opening_domino_id,
        "turn_started_at": (
            session.turn_started_at.isoformat()
            if session.turn_started_at is not None
            else None
        ),
        "turn_deadline_at": (
            session.turn_deadline_at.isoformat()
            if session.turn_deadline_at is not None
            else None
        ),
        "boneyard_count": len(session.boneyard or []),
        "table": _dominoes_with_mode(table, room.game_mode),
        "phone_open_ends": phone_ends,
        "phone_open_sum": phone_open_end_sum(table) if phone_ends else 0,
        "my_player_id": player_id,
        "my_hand": _dominoes_with_mode(my_hand, room.game_mode),
        "revealed_hands": revealed_hands,
        "round_result": session.last_round_result or None,
        "players": [
            {
                "id": player.id,
                "user_id": player.user_id,
                "name": player.name,
                "avatar_url": _avatar_url_for_player(player),
                "gender": _gender_for_player(player),
                "seat_index": player.seat_index,
                "is_owner": player.is_owner,
                "is_bot": player.is_bot,
                "is_active": player.is_active,
                "is_online": player.is_online,
                "last_seen_at": (
                    player.last_seen_at.isoformat()
                    if player.last_seen_at is not None
                    else None
                ),
                "score": int(scores.get(str(player.id), 0)),
                "domino_count": len(hands.get(str(player.id), [])),
                "active_gift": _serialize_active_gift(player),
            }
            for player in players
        ],
    }
