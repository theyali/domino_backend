from django.db import transaction
from django.utils import timezone

from rooms.models import GameRoom

from .engine import phone_playable_sides, playable_sides
from .models import GameSession
from .services import draw_domino, pass_turn, play_domino


@transaction.atomic
def process_expired_turn(*, room_id):
    """Process one expired server turn.

    Returns True only when the deadline was expired and the server performed
    an automatic game action. The row lock guarantees that concurrent
    heartbeat/API checks cannot process the same timeout twice.
    """
    try:
        session = (
            GameSession.objects.select_for_update()
            .select_related("room", "current_player")
            .prefetch_related("room__players")
            .get(room_id=room_id)
        )
    except GameSession.DoesNotExist:
        return False

    if session.status != GameSession.Status.ACTIVE:
        return False

    deadline = session.turn_deadline_at
    if deadline is None or deadline > timezone.now():
        return False

    active_player_ids = set(
        session.room.players.filter(is_active=True).values_list("id", flat=True)
    )
    player_id = session.current_player_id
    if player_id not in active_player_ids:
        return False

    hands = session.hands or {}
    hand = list(hands.get(str(player_id), []))
    table = [dict(item) for item in (session.table or [])]

    automatic_move = _first_automatic_move(
        session=session,
        hand=hand,
        table=table,
    )

    if automatic_move is not None:
        domino_id, side = automatic_move
        play_domino(
            room_id=room_id,
            player_id=player_id,
            domino_id=domino_id,
            side=side,
        )
        return True

    if session.boneyard:
        draw_domino(room_id=room_id, player_id=player_id)
        return True

    pass_turn(room_id=room_id, player_id=player_id)
    return True


def process_all_expired_turns():
    room_ids = list(
        GameSession.objects.filter(
            status=GameSession.Status.ACTIVE,
            turn_deadline_at__isnull=False,
            turn_deadline_at__lte=timezone.now(),
        ).values_list("room_id", flat=True)
    )

    processed = 0
    for room_id in room_ids:
        if process_expired_turn(room_id=room_id):
            processed += 1

    return processed


def _first_automatic_move(*, session, hand, table):
    if not table:
        for domino in hand:
            if domino["id"] == session.opening_domino_id:
                return domino["id"], "center"
        return None

    phone_mode = session.room.game_mode == GameRoom.GameMode.PHONE

    for domino in hand:
        sides = (
            phone_playable_sides(domino, table)
            if phone_mode
            else playable_sides(domino, table)
        )
        if not sides:
            continue

        if phone_mode:
            for side in ("top", "right", "bottom", "left"):
                if side in sides:
                    return domino["id"], side
        else:
            side = "left" if "left" in sides else "right"
            return domino["id"], side

    return None
