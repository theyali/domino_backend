from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import GameRoom, RoomPlayer
from .realtime import (
    broadcast_game_state_updated,
    broadcast_room_deleted,
    broadcast_room_updated,
)


def _next_free_seat(room):
    occupied = set(
        room.players.filter(is_active=True).values_list("seat_index", flat=True)
    )
    for seat_index in range(room.max_players):
        if seat_index not in occupied:
            return seat_index
    return None


def _player_name_for_user(user):
    if not getattr(user, "is_authenticated", False):
        raise ValidationError({"user": "Для входа за стол нужна авторизация."})

    full_name = (user.get_full_name() or "").strip()
    username = (getattr(user, "username", "") or "").strip()
    name = full_name or username or f"Игрок {user.pk}"
    return name[:40]


def _promote_new_owner(room):
    new_owner = (
        room.players.filter(is_active=True)
        .order_by("seat_index", "joined_at")
        .first()
    )

    if new_owner is None:
        return None

    room.players.filter(is_owner=True).exclude(pk=new_owner.pk).update(is_owner=False)
    if not new_owner.is_owner:
        new_owner.is_owner = True
        new_owner.save(update_fields=["is_owner"])

    room.owner_name = new_owner.name
    room.save(update_fields=["owner_name"])
    return new_owner


@transaction.atomic
def create_room(
    *,
    restaurant,
    user,
    max_players,
    game_mode=GameRoom.GameMode.CLASSIC_101,
    target_score=101,
    password="",
    name="",
):
    if not restaurant.is_active:
        raise ValidationError({"restaurant": "Этот ресторан сейчас неактивен."})

    if game_mode == GameRoom.GameMode.CLASSIC_101 and max_players != 2:
        raise ValidationError({"max_players": "Для правила 101 нужен стол на 2 игроков."})

    player_name = _player_name_for_user(user)

    room = GameRoom(
        restaurant=restaurant,
        owner_name=player_name,
        max_players=max_players,
        game_mode=game_mode,
        target_score=101 if game_mode == GameRoom.GameMode.CLASSIC_101 else target_score,
        name=(name or "").strip(),
    )
    room.set_password(password)
    room.save()

    RoomPlayer.objects.create(
        room=room,
        user=user,
        name=player_name,
        seat_index=0,
        is_owner=True,
        is_active=True,
        is_online=False,
    )
    return room


@transaction.atomic
def join_room(*, room_id, user, password="", bypass_password=False):
    room = (
        GameRoom.objects.select_for_update()
        .select_related("restaurant")
        .get(pk=room_id)
    )

    if room.status != GameRoom.Status.WAITING:
        raise ValidationError({"room": "Игра в этой комнате уже началась."})

    # bypass_password используется только сервером после принятия валидного
    # приглашения. Обычный HTTP join никогда не получает этот флаг от клиента.
    if not bypass_password and not room.check_room_password(password):
        raise ValidationError({"password": "Неверный пароль комнаты."})

    player_name = _player_name_for_user(user)

    existing = room.players.filter(user=user, is_active=True).first()
    if existing is not None:
        raise ValidationError({"room": "Ты уже находишься за этим столом."})

    if room.is_full:
        raise ValidationError({"room": "Комната уже заполнена."})

    seat_index = _next_free_seat(room)
    if seat_index is None:
        raise ValidationError({"room": "В комнате нет свободного места."})

    player = RoomPlayer.objects.create(
        room=room,
        user=user,
        name=player_name,
        seat_index=seat_index,
        is_owner=False,
        is_active=True,
        is_online=False,
    )

    transaction.on_commit(lambda: broadcast_room_updated(room.pk))
    return room, player


@transaction.atomic
def leave_room(*, room_id, player_id):
    room = GameRoom.objects.select_for_update().get(pk=room_id)

    try:
        player = room.players.get(pk=player_id, is_active=True)
    except RoomPlayer.DoesNotExist as exc:
        raise ValidationError({"player_id": "Игрок не найден в этой комнате."}) from exc

    was_owner = player.is_owner

    if room.status == GameRoom.Status.WAITING:
        player.delete()

        if not room.players.filter(is_active=True).exists():
            deleted_room_id = room.pk
            room.delete()
            transaction.on_commit(lambda: broadcast_room_deleted(deleted_room_id))
            return {"room_deleted": True}

        if was_owner:
            _promote_new_owner(room)

        transaction.on_commit(lambda: broadcast_room_updated(room.pk))
        return {"room_deleted": False}

    player.is_active = False
    player.is_owner = False
    player.is_online = False
    player.last_seen_at = timezone.now()
    player.presence_connection_token = ""
    player.save(
        update_fields=[
            "is_active",
            "is_owner",
            "is_online",
            "last_seen_at",
            "presence_connection_token",
        ]
    )

    active_players_exist = room.players.filter(is_active=True).exists()

    if not active_players_exist:
        deleted_room_id = room.pk
        room.delete()
        transaction.on_commit(lambda: broadcast_room_deleted(deleted_room_id))
        return {"room_deleted": True}

    if was_owner:
        _promote_new_owner(room)

    if room.status == GameRoom.Status.PLAYING:
        from game.services import finish_game_on_player_exit

        finish_game_on_player_exit(room_id=room.pk, player_id=player_id)

    transaction.on_commit(lambda: broadcast_room_updated(room.pk))
    transaction.on_commit(lambda: broadcast_game_state_updated(room.pk))
    return {"room_deleted": False}
