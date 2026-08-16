from .engine import phone_playable_sides, playable_sides
from .models import GameSession
from .services import draw_domino, pass_turn, play_domino


BOT_ACTION_LIMIT = 128


def _side_order(side):
    order = {
        "center": 0,
        "left": 1,
        "right": 2,
        "top": 1,
        "bottom": 3,
    }
    return order.get(side, 99)


def _choose_bot_move(session, hand, table):
    if not table:
        opening_id = session.opening_domino_id
        for domino in hand:
            if domino["id"] == opening_id:
                return domino["id"], "center"
        return None

    phone_mode = session.room.game_mode == "phone"
    candidates = []
    for domino in hand:
        sides = (
            phone_playable_sides(domino, table)
            if phone_mode
            else playable_sides(domino, table)
        )
        for side in sides:
            candidates.append(
                (
                    -(domino["left"] + domino["right"]),
                    0 if domino["left"] == domino["right"] else 1,
                    _side_order(side),
                    domino["id"],
                    side,
                )
            )

    if not candidates:
        return None

    candidates.sort()
    chosen = candidates[0]
    return chosen[3], chosen[4]


def process_bot_turns(*, room_id, max_actions=BOT_ACTION_LIMIT):
    """Plays consecutive server-authoritative bot turns until a human must act."""
    actions = 0

    while actions < max_actions:
        try:
            session = (
                GameSession.objects.select_related("room", "current_player")
                .get(room_id=room_id)
            )
        except GameSession.DoesNotExist:
            return actions

        if session.status != GameSession.Status.ACTIVE:
            return actions

        bot = session.current_player
        if bot is None or not bot.is_active or not bot.is_bot:
            return actions

        hands = session.hands or {}
        hand = [dict(item) for item in hands.get(str(bot.id), [])]
        table = [dict(item) for item in (session.table or [])]
        move = _choose_bot_move(session, hand, table)

        if move is not None:
            domino_id, side = move
            play_domino(
                room_id=room_id,
                player_id=bot.id,
                domino_id=domino_id,
                side=side,
            )
        elif session.boneyard:
            draw_domino(room_id=room_id, player_id=bot.id)
        else:
            pass_turn(room_id=room_id, player_id=bot.id)

        actions += 1

    raise RuntimeError(
        f"Bot action guard exceeded for room {room_id}: {max_actions} actions."
    )
