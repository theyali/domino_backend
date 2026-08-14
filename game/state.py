from django.utils import timezone


def _serialize_active_gift(player):
    gift = player.active_gift
    if gift is None:
        return None

    return {
        "id": gift.id,
        "restaurant_id": gift.restaurant_id,
        "name": gift.name,
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


def serialize_game_state_for_player(session, player_id):
    room = session.room
    players = list(room.players.all())
    hands = session.hands or {}
    scores = session.scores or {}
    my_hand = hands.get(str(player_id), [])

    return {
        "game_id": session.pk,
        "room_id": room.pk,
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
        "table": session.table or [],
        "my_player_id": player_id,
        "my_hand": my_hand,
        "round_result": session.last_round_result or None,
        "players": [
            {
                "id": player.id,
                "user_id": player.user_id,
                "name": player.name,
                "avatar_url": _avatar_url_for_player(player),
                "seat_index": player.seat_index,
                "is_owner": player.is_owner,
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
