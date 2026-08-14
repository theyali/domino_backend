from django.db import transaction
from rest_framework.exceptions import ValidationError

from rooms.models import GameRoom, RoomPlayer
from rooms.realtime import broadcast_game_started, broadcast_game_state_updated

from .engine import deal_round, find_domino, orient_domino_for_side, playable_sides
from .models import GameSession
from .state import serialize_game_state_for_player


@transaction.atomic
def start_game(*, room_id, player_id):
    room = (
        GameRoom.objects.select_for_update()
        .prefetch_related("players")
        .get(pk=room_id)
    )

    players = list(room.players.all())
    local_player = next((player for player in players if player.pk == player_id), None)

    if local_player is None:
        raise ValidationError({"player_id": "Игрок не найден в этой комнате."})

    if not local_player.is_owner:
        raise ValidationError({"player_id": "Только создатель комнаты может начать игру."})

    existing_session = GameSession.objects.filter(room=room).first()
    if existing_session is not None:
        return existing_session

    if room.status != GameRoom.Status.WAITING:
        raise ValidationError({"room": "Эта игра уже была запущена."})

    if len(players) != room.max_players:
        raise ValidationError(
            {"room": f"Нужно дождаться всех игроков: {len(players)} / {room.max_players}."}
        )

    round_data = deal_round(players)
    opening_player = next(
        player
        for player in players
        if player.pk == round_data["opening_player_id"]
    )

    session = GameSession.objects.create(
        room=room,
        current_player=opening_player,
        opening_player=opening_player,
        opening_domino_id=round_data["opening_domino_id"],
        hands=round_data["hands"],
        boneyard=round_data["boneyard"],
        table=[],
        scores={str(player.pk): 0 for player in players},
    )

    room.status = GameRoom.Status.PLAYING
    room.save(update_fields=["status"])

    transaction.on_commit(lambda: broadcast_game_started(room.pk))
    return session


@transaction.atomic
def play_domino(*, room_id, player_id, domino_id, side):
    session, players, player, hands, hand, table = _locked_turn_context(
        room_id=room_id,
        player_id=player_id,
    )

    domino = find_domino(hand, domino_id)
    if domino is None:
        raise ValidationError({"domino_id": "Этой костяшки нет в вашей руке."})

    if not table:
        if domino_id != session.opening_domino_id:
            raise ValidationError(
                {"domino_id": "Первый ход нужно сделать отмеченной сервером костяшкой."}
            )
        if side != "center":
            raise ValidationError({"side": "Первую костяшку положите в центр."})
    else:
        sides = playable_sides(domino, table)
        if not sides:
            raise ValidationError({"domino_id": "Эта костяшка сейчас не подходит."})
        if side == "center":
            raise ValidationError(
                {"side": "После первого хода выберите левую или правую сторону."}
            )
        if side not in sides:
            edge_name = "левому" if side == "left" else "правому"
            raise ValidationError({"side": f"Эта костяшка не подходит к {edge_name} краю."})

    try:
        oriented = orient_domino_for_side(domino, table, side)
    except ValueError as error:
        raise ValidationError({"side": str(error)}) from error

    played_domino = {
        **oriented,
        "played_by_player_id": player_id,
        "side": side,
        "move_number": len(table) + 1,
    }

    hand = [item for item in hand if item["id"] != domino_id]
    hands[str(player_id)] = hand

    if side == "left":
        table.insert(0, played_domino)
    else:
        table.append(played_domino)

    next_player = _next_player(players, current_player_id=player_id)

    session.hands = hands
    session.table = table
    session.current_player = next_player
    session.version += 1
    session.save(
        update_fields=[
            "hands",
            "table",
            "current_player",
            "version",
            "updated_at",
        ]
    )

    transaction.on_commit(lambda: broadcast_game_state_updated(session.room_id))
    return session


@transaction.atomic
def draw_domino(*, room_id, player_id):
    session, players, player, hands, hand, table = _locked_turn_context(
        room_id=room_id,
        player_id=player_id,
    )

    if _has_legal_play(session=session, hand=hand, table=table):
        raise ValidationError(
            {"game": "У вас уже есть подходящая костяшка. Сначала сделайте ход."}
        )

    boneyard = [dict(item) for item in (session.boneyard or [])]
    if not boneyard:
        raise ValidationError(
            {"game": "Базар пуст. Если ходов нет, используйте пас."}
        )

    drawn_domino = boneyard.pop()
    hand.append(drawn_domino)
    hands[str(player_id)] = hand

    session.hands = hands
    session.boneyard = boneyard
    session.version += 1
    session.save(
        update_fields=[
            "hands",
            "boneyard",
            "version",
            "updated_at",
        ]
    )

    transaction.on_commit(lambda: broadcast_game_state_updated(session.room_id))
    return session


@transaction.atomic
def pass_turn(*, room_id, player_id):
    session, players, player, hands, hand, table = _locked_turn_context(
        room_id=room_id,
        player_id=player_id,
    )

    if _has_legal_play(session=session, hand=hand, table=table):
        raise ValidationError(
            {"game": "Пас запрещён: у вас есть подходящая костяшка."}
        )

    if session.boneyard:
        raise ValidationError(
            {"game": "Пас пока запрещён: в базаре ещё есть костяшки."}
        )

    session.current_player = _next_player(players, current_player_id=player_id)
    session.version += 1
    session.save(
        update_fields=[
            "current_player",
            "version",
            "updated_at",
        ]
    )

    transaction.on_commit(lambda: broadcast_game_state_updated(session.room_id))
    return session


def _locked_turn_context(*, room_id, player_id):
    session = (
        GameSession.objects.select_for_update()
        .select_related("room", "current_player", "opening_player")
        .prefetch_related("room__players")
        .get(room_id=room_id)
    )

    if session.status != GameSession.Status.ACTIVE:
        raise ValidationError({"game": "Эта партия уже завершена."})

    players = list(session.room.players.all())
    player = next((item for item in players if item.pk == player_id), None)

    if player is None:
        raise ValidationError({"player_id": "Игрок не найден в этой комнате."})

    if session.current_player_id != player_id:
        raise ValidationError({"player_id": "Сейчас ход другого игрока."})

    hands = {key: list(value) for key, value in (session.hands or {}).items()}
    hand = list(hands.get(str(player_id), []))
    table = [dict(item) for item in (session.table or [])]

    return session, players, player, hands, hand, table


def _has_legal_play(*, session, hand, table):
    if not table:
        return any(item["id"] == session.opening_domino_id for item in hand)

    return any(playable_sides(item, table) for item in hand)


def _next_player(players, *, current_player_id):
    ordered = sorted(players, key=lambda player: player.seat_index)

    for index, player in enumerate(ordered):
        if player.pk == current_player_id:
            return ordered[(index + 1) % len(ordered)]

    raise ValidationError({"player_id": "Не удалось определить следующего игрока."})


def game_state_for_player(*, session, player_id):
    return serialize_game_state_for_player(session, player_id)
