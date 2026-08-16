from datetime import timedelta

from django.utils import timezone

from .models import GameRoom, RoomPlayer
from .realtime import broadcast_room_deleted

DEFAULT_STALE_ROOM_MINUTES = 30
DEFAULT_PRESENCE_STALE_SECONDS = 35


def mark_player_online(*, room_id, player_id, connection_token=None):
    updates = {
        "is_online": True,
        "last_seen_at": timezone.now(),
    }
    if connection_token is not None:
        updates["presence_connection_token"] = connection_token

    return RoomPlayer.objects.filter(
        pk=player_id,
        room_id=room_id,
        is_active=True,
        is_bot=False,
    ).update(**updates)


def touch_player(*, room_id, player_id, connection_token=None):
    queryset = RoomPlayer.objects.filter(
        pk=player_id,
        room_id=room_id,
        is_active=True,
        is_bot=False,
    )
    if connection_token is not None:
        queryset = queryset.filter(presence_connection_token=connection_token)

    return queryset.update(
        is_online=True,
        last_seen_at=timezone.now(),
    )


def mark_player_offline(*, room_id, player_id, connection_token=None):
    queryset = RoomPlayer.objects.filter(
        pk=player_id,
        room_id=room_id,
        is_active=True,
        is_bot=False,
    )
    if connection_token is not None:
        queryset = queryset.filter(presence_connection_token=connection_token)

    return queryset.update(
        is_online=False,
        last_seen_at=timezone.now(),
        presence_connection_token="",
    )


def mark_stale_players_offline(
    *,
    room_id,
    seconds=DEFAULT_PRESENCE_STALE_SECONDS,
):
    cutoff = timezone.now() - timedelta(seconds=seconds)
    return RoomPlayer.objects.filter(
        room_id=room_id,
        is_active=True,
        is_bot=False,
        is_online=True,
        last_seen_at__lt=cutoff,
    ).update(
        is_online=False,
        presence_connection_token="",
    )


def cleanup_stale_rooms(*, minutes=DEFAULT_STALE_ROOM_MINUTES, restaurant_id=None):
    cutoff = timezone.now() - timedelta(minutes=minutes)
    rooms = GameRoom.objects.prefetch_related("players").all()

    if restaurant_id is not None:
        rooms = rooms.filter(restaurant_id=restaurant_id)

    deleted_room_ids = []

    for room in rooms:
        active_players = [
            player
            for player in room.players.all()
            if player.is_active and not player.is_bot
        ]
        has_recent_player = any(
            player.last_seen_at is not None and player.last_seen_at >= cutoff
            for player in active_players
        )

        if has_recent_player:
            continue

        room_id = room.pk
        room.delete()
        broadcast_room_deleted(room_id)
        deleted_room_ids.append(room_id)

    return deleted_room_ids
