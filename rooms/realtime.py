from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def room_group_name(room_id: int) -> str:
    return f"room_{room_id}"


def _group_send(room_id: int, event: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(room_group_name(room_id), event)


def broadcast_room_updated(room_id: int) -> None:
    _group_send(
        room_id,
        {
            "type": "room.updated",
            "room_id": room_id,
        },
    )


def broadcast_room_deleted(room_id: int) -> None:
    _group_send(
        room_id,
        {
            "type": "room.deleted",
            "room_id": room_id,
        },
    )


def broadcast_game_started(room_id: int) -> None:
    _group_send(
        room_id,
        {
            "type": "game.started",
            "room_id": room_id,
        },
    )


def broadcast_game_state_updated(room_id: int) -> None:
    _group_send(
        room_id,
        {
            "type": "game.state.updated",
            "room_id": room_id,
        },
    )


def broadcast_gift_sent(
    *,
    room_id: int,
    event_id: str,
    sender_player_id: int,
    recipient_player_ids: list[int],
    gift: dict,
) -> None:
    _group_send(
        room_id,
        {
            "type": "gift.sent",
            "event_id": event_id,
            "sender_player_id": sender_player_id,
            "recipient_player_ids": recipient_player_ids,
            "gift": gift,
        },
    )
