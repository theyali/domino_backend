from django.db import transaction
from rest_framework.exceptions import ValidationError

from rooms.models import GameRoom, RoomPlayer
from rooms.realtime import broadcast_game_started, broadcast_game_state_updated

from .engine import deal_round, find_domino, orient_domino_for_side, playable_sides
from .models import GameSession
from .state import serialize_game_state_for_player

LOSING_SCORE = 101
MINIMUM_PENALTY_TO_RECORD = 13
DOUBLE_BLANK_PENALTY_WHEN_ALONE = 25


@transaction.atomic
def start_game(*, room_id, player_id):
    room = (
        GameRoom.objects.select_for_update()
        .prefetch_related("players")
        .get(pk=room_id)
    )

    players = list(room.players.filter(is_active=True))
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
        consecutive_passes=0,
        last_round_result={},
    )

    room.status = GameRoom.Status.PLAYING
    room.save(update_fields=["status"])

    transaction.on_commit(lambda: broadcast_game_started(room.pk))
    return session


@transaction.atomic
def start_next_round(*, room_id, player_id):
    session = (
        GameSession.objects.select_for_update()
        .select_related("room", "current_player", "opening_player")
        .prefetch_related("room__players")
        .get(room_id=room_id)
    )
    room = session.room
    players = list(room.players.filter(is_active=True))
    local_player = next((player for player in players if player.pk == player_id), None)

    if local_player is None:
        raise ValidationError({"player_id": "Игрок не найден в этой комнате."})

    if not local_player.is_owner:
        raise ValidationError({"player_id": "Только создатель комнаты может начать следующий раунд."})

    if session.status != GameSession.Status.ROUND_FINISHED:
        raise ValidationError({"game": "Следующий раунд сейчас нельзя запустить."})

    if len(players) < 2:
        raise ValidationError({"game": "Для следующего раунда нужно минимум два игрока."})

    round_data = deal_round(players)
    opening_player = next(
        player
        for player in players
        if player.pk == round_data["opening_player_id"]
    )

    session.status = GameSession.Status.ACTIVE
    session.round_number += 1
    session.current_player = opening_player
    session.opening_player = opening_player
    session.opening_domino_id = round_data["opening_domino_id"]
    session.hands = round_data["hands"]
    session.boneyard = round_data["boneyard"]
    session.table = []
    session.consecutive_passes = 0
    session.last_round_result = {}
    session.version += 1
    session.save(
        update_fields=[
            "status",
            "round_number",
            "current_player",
            "opening_player",
            "opening_domino_id",
            "hands",
            "boneyard",
            "table",
            "consecutive_passes",
            "last_round_result",
            "version",
            "updated_at",
        ]
    )

    if room.status != GameRoom.Status.PLAYING:
        room.status = GameRoom.Status.PLAYING
        room.save(update_fields=["status"])

    transaction.on_commit(lambda: broadcast_game_state_updated(room.pk))
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

    session.hands = hands
    session.table = table
    session.consecutive_passes = 0

    if hand:
        session.current_player = _next_player(players, current_player_id=player_id)
    else:
        _finish_round(
            session=session,
            players=players,
            reason="domino",
            winner_player_ids=[player_id],
        )

    session.version += 1
    update_fields = [
        "hands",
        "table",
        "consecutive_passes",
        "version",
        "updated_at",
    ]

    if session.status == GameSession.Status.ACTIVE:
        update_fields.append("current_player")
    else:
        update_fields.extend(["status", "scores", "last_round_result"])

    session.save(update_fields=update_fields)

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
    session.consecutive_passes = 0
    session.version += 1
    session.save(
        update_fields=[
            "hands",
            "boneyard",
            "consecutive_passes",
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

    session.consecutive_passes += 1

    if session.consecutive_passes >= len(players):
        hand_points = _all_hand_points(players=players, hands=hands)
        minimum = min(hand_points.values())
        winner_ids = [
            player.pk
            for player in players
            if hand_points[player.pk] == minimum
        ]
        _finish_round(
            session=session,
            players=players,
            reason="fish",
            winner_player_ids=winner_ids,
            precomputed_hand_points=hand_points,
        )
    else:
        session.current_player = _next_player(players, current_player_id=player_id)

    session.version += 1
    update_fields = [
        "consecutive_passes",
        "version",
        "updated_at",
    ]

    if session.status == GameSession.Status.ACTIVE:
        update_fields.append("current_player")
    else:
        update_fields.extend(["status", "scores", "last_round_result"])

    session.save(update_fields=update_fields)

    transaction.on_commit(lambda: broadcast_game_state_updated(session.room_id))
    return session


@transaction.atomic
def finish_game_on_player_exit(*, room_id, player_id):
    try:
        session = (
            GameSession.objects.select_for_update()
            .select_related("room", "current_player", "opening_player")
            .prefetch_related("room__players")
            .get(room_id=room_id)
        )
    except GameSession.DoesNotExist:
        return None

    if session.status == GameSession.Status.FINISHED:
        return session

    room = session.room
    players = list(room.players.all())
    active_winners = [
        player.pk
        for player in players
        if player.is_active and player.pk != player_id
    ]
    hands = {key: list(value) for key, value in (session.hands or {}).items()}
    hand_points = _all_hand_points(players=players, hands=hands)
    scores = {str(key): int(value) for key, value in (session.scores or {}).items()}

    session.status = GameSession.Status.FINISHED
    session.last_round_result = {
        "reason": "player_left",
        "winner_player_ids": active_winners,
        "hand_points": {str(key): value for key, value in hand_points.items()},
        "added_penalties": {str(player.pk): 0 for player in players},
        "total_scores": scores,
        "match_loser_player_ids": [player_id],
        "match_winner_player_ids": active_winners,
        "left_player_id": player_id,
    }
    session.version += 1
    session.save(
        update_fields=[
            "status",
            "last_round_result",
            "version",
            "updated_at",
        ]
    )

    room.status = GameRoom.Status.FINISHED
    room.save(update_fields=["status"])

    transaction.on_commit(lambda: broadcast_game_state_updated(room.pk))
    return session


def _finish_round(
    *,
    session,
    players,
    reason,
    winner_player_ids,
    precomputed_hand_points=None,
):
    hands = {key: list(value) for key, value in (session.hands or {}).items()}
    hand_points = precomputed_hand_points or _all_hand_points(
        players=players,
        hands=hands,
    )
    winner_ids = set(winner_player_ids)
    scores = {str(key): int(value) for key, value in (session.scores or {}).items()}
    added_penalties = {str(player.pk): 0 for player in players}

    for player in players:
        if player.pk in winner_ids:
            continue

        penalty = hand_points[player.pk]
        if penalty >= MINIMUM_PENALTY_TO_RECORD:
            scores[str(player.pk)] = int(scores.get(str(player.pk), 0)) + penalty
            added_penalties[str(player.pk)] = penalty

    match_loser_ids = [
        player.pk
        for player in players
        if int(scores.get(str(player.pk), 0)) >= LOSING_SCORE
    ]
    match_winner_ids = [
        player.pk
        for player in players
        if player.pk not in match_loser_ids
    ]

    session.scores = scores
    session.status = (
        GameSession.Status.FINISHED
        if match_loser_ids
        else GameSession.Status.ROUND_FINISHED
    )
    session.last_round_result = {
        "reason": reason,
        "winner_player_ids": list(winner_player_ids),
        "hand_points": {str(key): value for key, value in hand_points.items()},
        "added_penalties": added_penalties,
        "total_scores": scores,
        "match_loser_player_ids": match_loser_ids,
        "match_winner_player_ids": match_winner_ids,
    }

    if match_loser_ids:
        session.room.status = GameRoom.Status.FINISHED
        session.room.save(update_fields=["status"])


def _all_hand_points(*, players, hands):
    return {
        player.pk: _hand_points(hands.get(str(player.pk), []))
        for player in players
    }


def _hand_points(hand):
    if (
        len(hand) == 1
        and hand[0]["left"] == 0
        and hand[0]["right"] == 0
    ):
        return DOUBLE_BLANK_PENALTY_WHEN_ALONE

    return sum(item["left"] + item["right"] for item in hand)


def _locked_turn_context(*, room_id, player_id):
    session = (
        GameSession.objects.select_for_update()
        .select_related("room", "current_player", "opening_player")
        .prefetch_related("room__players")
        .get(room_id=room_id)
    )

    if session.status != GameSession.Status.ACTIVE:
        raise ValidationError({"game": "Сейчас нельзя делать ход: раунд уже завершён."})

    players = list(session.room.players.filter(is_active=True))
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
