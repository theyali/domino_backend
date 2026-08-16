from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from rooms.models import GameRoom, RoomPlayer
from rooms.realtime import broadcast_gift_sent

from .models import Gift, InventoryGift


@transaction.atomic
def send_gift_to_room_players(
    *,
    sender_user,
    room_id,
    gift_id,
    recipient_player_ids,
):
    try:
        room = (
            GameRoom.objects.select_for_update()
            .select_related("restaurant")
            .get(pk=room_id)
        )
    except GameRoom.DoesNotExist as exc:
        raise ValidationError({"room": "Игровой стол больше не существует."}) from exc

    if room.status != GameRoom.Status.PLAYING:
        raise ValidationError({"room": "Подарки можно отправлять во время активной игры."})

    try:
        sender_player = RoomPlayer.objects.select_for_update().get(
            room=room,
            user=sender_user,
            is_active=True,
        )
    except RoomPlayer.DoesNotExist as exc:
        raise ValidationError(
            {"sender": "Твой аккаунт не привязан к игроку за этим столом."}
        ) from exc

    recipient_ids = list(dict.fromkeys(int(value) for value in recipient_player_ids))
    if not recipient_ids:
        raise ValidationError({"recipients": "Выбери хотя бы одного получателя."})

    # Do not select_related("user") on this SELECT ... FOR UPDATE query.
    # RoomPlayer.user is nullable, so PostgreSQL would produce a LEFT OUTER JOIN
    # and reject the lock with:
    # "FOR UPDATE cannot be applied to the nullable side of an outer join".
    # There are at most four recipients, so loading user objects lazily below is
    # cheap and, more importantly, keeps the row lock limited to RoomPlayer.
    recipients = list(
        RoomPlayer.objects.select_for_update()
        .filter(
            room=room,
            id__in=recipient_ids,
            is_active=True,
        )
        .order_by("seat_index")
    )

    if len(recipients) != len(recipient_ids):
        raise ValidationError({"recipients": "Один из получателей уже не находится за столом."})

    if any(player.user_id is None for player in recipients):
        raise ValidationError(
            {"recipients": "Один из игроков вошёл в старую комнату без аккаунта. Создай новый стол."}
        )

    try:
        gift = (
            Gift.objects.select_for_update()
            .filter(
                Q(restaurant=room.restaurant) | Q(restaurant__isnull=True),
                is_active=True,
            )
            .get(pk=gift_id)
        )
    except Gift.DoesNotExist as exc:
        raise ValidationError(
            {"gift": "Этот подарок недоступен в текущем ресторане."}
        ) from exc

    inventory_items = list(
        InventoryGift.objects.select_for_update()
        .filter(
            owner=sender_user,
            gift=gift,
            status=InventoryGift.Status.AVAILABLE,
            is_giftable=True,
        )
        .order_by("id")[: len(recipients)]
    )

    if len(inventory_items) < len(recipients):
        raise ValidationError(
            {
                "gift": (
                    f"Недостаточно экземпляров «{gift.name}» для отправки. "
                    f"Нужно: {len(recipients)}, есть: {len(inventory_items)}."
                )
            }
        )

    now = timezone.now()
    transferred_inventory_ids = []

    for inventory_item, recipient in zip(inventory_items, recipients, strict=True):
        inventory_item.owner = recipient.user
        inventory_item.is_giftable = False
        inventory_item.gifted_by = sender_user
        inventory_item.gifted_at = now
        inventory_item.save(
            update_fields=[
                "owner",
                "is_giftable",
                "gifted_by",
                "gifted_at",
            ]
        )
        transferred_inventory_ids.append(inventory_item.id)

        recipient.active_gift = gift
        recipient.save(update_fields=["active_gift"])

    event_id = uuid4().hex
    gift_payload = {
        "id": gift.id,
        "restaurant_id": gift.restaurant_id,
        "is_global": gift.is_global,
        "name": gift.name,
        "level": gift.level,
        "image_url": gift.image.url if gift.image else None,
    }

    recipient_player_ids = [player.id for player in recipients]

    # The database transfer is authoritative. A temporary Redis/Channels publish
    # failure must not turn an already committed gift transfer into HTTP 500.
    # Django logs a robust on_commit callback failure while the REST request can
    # still return the successful authoritative result to Flutter.
    transaction.on_commit(
        lambda: broadcast_gift_sent(
            room_id=room.id,
            event_id=event_id,
            sender_player_id=sender_player.id,
            recipient_player_ids=recipient_player_ids,
            gift=gift_payload,
        ),
        robust=True,
    )

    return {
        "event_id": event_id,
        "sender_player_id": sender_player.id,
        "recipient_player_ids": recipient_player_ids,
        "gift": gift_payload,
        "transferred_inventory_ids": transferred_inventory_ids,
        "sent_at": now.isoformat(),
    }
