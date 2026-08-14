from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import GameRoom, RoomPlayer
from .realtime import broadcast_room_deleted, broadcast_room_updated


def _next_free_seat(room):
    occupied = set(room.players.values_list("seat_index", flat=True))
    for seat_index in range(room.max_players):
        if seat_index not in occupied:
            return seat_index
    return None


@transaction.atomic
def create_room(*, restaurant, owner_name, max_players, password="", name=""):
    if not restaurant.is_active:
        raise ValidationError({"restaurant": "Этот ресторан сейчас неактивен."})

    room = GameRoom(
        restaurant=restaurant,
        owner_name=owner_name,
        max_players=max_players,
        name=(name or "").strip(),
    )
    room.set_password(password)
    room.save()

    RoomPlayer.objects.create(
        room=room,
        name=owner_name,
        seat_index=0,
        is_owner=True,
    )
    return room


@transaction.atomic
def join_room(*, room_id, player_name, password=""):
    room = (
        GameRoom.objects.select_for_update()
        .select_related("restaurant")
        .get(pk=room_id)
    )

    if room.status != GameRoom.Status.WAITING:
        raise ValidationError({"room": "Игра в этой комнате уже началась."})

    if not room.check_room_password(password):
        raise ValidationError({"password": "Неверный пароль комнаты."})

    if room.is_full:
        raise ValidationError({"room": "Комната уже заполнена."})

    seat_index = _next_free_seat(room)
    if seat_index is None:
        raise ValidationError({"room": "В комнате нет свободного места."})

    player = RoomPlayer.objects.create(
        room=room,
        name=player_name,
        seat_index=seat_index,
        is_owner=False,
    )

    transaction.on_commit(lambda: broadcast_room_updated(room.pk))
    return room, player


@transaction.atomic
def leave_room(*, room_id, player_id):
    room = GameRoom.objects.select_for_update().get(pk=room_id)

    if room.status != GameRoom.Status.WAITING:
        raise ValidationError(
            {"room": "Выход из уже начавшейся игры добавим на этапе reconnect."}
        )

    try:
        player = room.players.get(pk=player_id)
    except RoomPlayer.DoesNotExist as exc:
        raise ValidationError({"player_id": "Игрок не найден в этой комнате."}) from exc

    if player.is_owner:
        deleted_room_id = room.pk
        room.delete()
        transaction.on_commit(lambda: broadcast_room_deleted(deleted_room_id))
        return {"room_deleted": True}

    player.delete()
    transaction.on_commit(lambda: broadcast_room_updated(room.pk))
    return {"room_deleted": False}
