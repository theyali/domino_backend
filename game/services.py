from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.ranking import record_match_statistics
from rooms.models import GameRoom, RoomPlayer
from rooms.realtime import broadcast_game_started, broadcast_game_state_updated

from .engine import (
    deal_round,
    find_domino,
    orient_domino_for_side,
    orient_phone_domino_for_side,
    phone_open_end_sum,
    phone_playable_sides,
    playable_sides,
)
from .models import GameSession
from .state import serialize_game_state_for_player
from .turn_clock import clear_turn_clock, reset_turn_clock

LOSING_SCORE = 101


def _is_phone(session):
    return session.room.game_mode == GameRoom.GameMode.PHONE


def _deal_for_room(room, players):
    return deal_round(
        players,
        require_double=room.game_mode == GameRoom.GameMode.PHONE,
    )


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
        if (
            existing_session.status == GameSession.Status.ACTIVE
            and existing_session.turn_deadline_at is None
        ):
            reset_turn_clock(existing_session)
            existing_session.save(
                update_fields=[
                    "turn_started_at",
                    "turn_deadline_at",
                    "updated_at",
                ]
            )
        return existing_session

    if room.status != GameRoom.Status.WAITING:
        raise ValidationError({"room": "Эта игра уже была запущена."})

    if len(players) != room.max_players:
        raise ValidationError(
            {"room": f"Нужно дождаться всех игроков: {len(players)} / {room.max_players}."}
        )

    if room.game_mode == GameRoom.GameMode.CLASSIC_101 and len(players) != 2:
        raise ValidationError({"room": "Правило 101 играется вдвоём."})

    round_data = _deal_for_room(room, players)
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
    reset_turn_clock(session)
    session.save(
        update_fields=[
            "turn_started_at",
            "turn_deadline_at",
            "updated_at",
        ]
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

    round_data = _deal_for_room(room, players)
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
    reset_turn_clock(session)
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
            "turn_started_at",
            "turn_deadline_at",
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

    phone_mode = _is_phone(session)

    if not table:
        if domino_id != session.opening_domino_id:
            raise ValidationError(
                {"domino_id": "Первый ход нужно сделать отмеченной сервером костяшкой."}
            )
        if side != "center":
            raise ValidationError({"side": "Первую костяшку положите в центр."})
        if phone_mode and domino["left"] != domino["right"]:
            raise ValidationError({"domino_id": "Телефон должен начинаться с дубля."})
        oriented = dict(domino)
    else:
        sides = (
            phone_playable_sides(domino, table)
            if phone_mode
            else playable_sides(domino, table)
        )
        if not sides:
            raise ValidationError({"domino_id": "Эта костяшка сейчас не подходит."})
        if side == "center":
            message = (
                "После первого хода выберите сторону креста."
                if phone_mode
                else "После первого хода выберите левую или правую сторону."
            )
            raise ValidationError({"side": message})
        if side not in sides:
            raise ValidationError({"side": "Эта костяшка не подходит к выбранному краю."})

        try:
            oriented = (
                orient_phone_domino_for_side(domino, table, side)
                if phone_mode
                else orient_domino_for_side(domino, table, side)
            )
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

    if phone_mode:
        # В «Телефоне» table хранится в хронологическом порядке; side
        # определяет одну из четырёх независимых веток креста.
        table.append(played_domino)
    elif side == "left":
        table.insert(0, played_domino)
    else:
        table.append(played_domino)

    session.hands = hands
    session.table = table
    session.consecutive_passes = 0

    move_points = 0
    if phone_mode and table:
        open_sum = phone_open_end_sum(table)
        if open_sum > 0 and open_sum % 5 == 0:
            move_points = open_sum // 5
            scores = {
                str(key): int(value)
                for key, value in (session.scores or {}).items()
            }
            scores[str(player_id)] = int(scores.get(str(player_id), 0)) + move_points
            session.scores = scores

    if phone_mode and int(session.scores.get(str(player_id), 0)) >= session.room.target_score:
        _finish_phone_match(
            session=session,
            players=players,
            winner_player_ids=[player_id],
            reason="target_score",
            added_points={str(player.pk): (move_points if player.pk == player_id else 0) for player in players},
        )
    elif hand:
        session.current_player = _next_player(players, current_player_id=player_id)
        reset_turn_clock(session)
    else:
        _finish_round(
            session=session,
            players=players,
            reason="domino",
            winner_player_ids=[player_id],
            move_points=move_points,
        )

    session.version += 1
    update_fields = [
        "hands",
        "table",
        "consecutive_passes",
        "turn_started_at",
        "turn_deadline_at",
        "version",
        "updated_at",
    ]

    if phone_mode:
        update_fields.append("scores")

    if session.status == GameSession.Status.ACTIVE:
        update_fields.append("current_player")
    else:
        update_fields.extend(["status", "scores", "last_round_result"])

    session.save(update_fields=list(dict.fromkeys(update_fields)))

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
    reset_turn_clock(session)
    session.version += 1
    session.save(
        update_fields=[
            "hands",
            "boneyard",
            "consecutive_passes",
            "turn_started_at",
            "turn_deadline_at",
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
        reset_turn_clock(session)

    session.version += 1
    update_fields = [
        "consecutive_passes",
        "turn_started_at",
        "turn_deadline_at",
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
        "added_points": {str(player.pk): 0 for player in players},
        "total_scores": scores,
        "match_loser_player_ids": [player_id],
        "match_winner_player_ids": active_winners,
        "left_player_id": player_id,
    }
    clear_turn_clock(session)
    session.version += 1
    session.save(
        update_fields=[
            "status",
            "last_round_result",
            "turn_started_at",
            "turn_deadline_at",
            "version",
            "updated_at",
        ]
    )

    record_match_statistics(
        session=session,
        players=players,
        winner_player_ids=active_winners,
        loser_player_ids=[player_id],
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
    move_points=0,
):
    if _is_phone(session):
        return _finish_phone_round(
            session=session,
            players=players,
            reason=reason,
            winner_player_ids=winner_player_ids,
            precomputed_hand_points=precomputed_hand_points,
            move_points=move_points,
        )

    return _finish_101_round(
        session=session,
        players=players,
        reason=reason,
        winner_player_ids=winner_player_ids,
        precomputed_hand_points=precomputed_hand_points,
    )


def _finish_101_round(
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
    scores = {str(key): int(value) for key, value in (session.scores or {}).items()}
    added_penalties = {str(player.pk): 0 for player in players}

    # 101: штраф равен точной сумме точек на оставшихся костяшках.
    # При обычном завершении у победителя рука пустая (0). При «рыбе»
    # каждый игрок получает штраф за собственную оставшуюся руку.
    for player in players:
        penalty = hand_points[player.pk]
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
        "added_points": {str(player.pk): 0 for player in players},
        "total_scores": scores,
        "match_loser_player_ids": match_loser_ids,
        "match_winner_player_ids": match_winner_ids,
    }
    clear_turn_clock(session)

    if match_loser_ids:
        session.room.status = GameRoom.Status.FINISHED
        session.room.save(update_fields=["status"])
        record_match_statistics(
            session=session,
            players=players,
            winner_player_ids=match_winner_ids,
            loser_player_ids=match_loser_ids,
        )


def _finish_phone_round(
    *,
    session,
    players,
    reason,
    winner_player_ids,
    precomputed_hand_points=None,
    move_points=0,
):
    hands = {key: list(value) for key, value in (session.hands or {}).items()}
    hand_points = precomputed_hand_points or _all_hand_points(
        players=players,
        hands=hands,
    )
    winner_ids = list(dict.fromkeys(winner_player_ids))
    winner_set = set(winner_ids)
    scores = {str(key): int(value) for key, value in (session.scores or {}).items()}
    added_points = {str(player.pk): 0 for player in players}

    # Очки за кратную пяти сумму концов уже могли быть начислены этим ходом.
    if len(winner_ids) == 1 and move_points:
        added_points[str(winner_ids[0])] += move_points

    # Бонус окончания раунда: складываем точки на руках проигравших,
    # округляем к ближайшей пятёрке и переводим в активные очки /5.
    bonus_pips = sum(
        hand_points[player.pk]
        for player in players
        if player.pk not in winner_set
    )
    bonus_units = (bonus_pips + 2) // 5

    if winner_ids and bonus_units > 0:
        base_bonus = bonus_units // len(winner_ids)
        remainder = bonus_units % len(winner_ids)
        for index, winner_id in enumerate(winner_ids):
            bonus = base_bonus + (1 if index < remainder else 0)
            if bonus <= 0:
                continue
            scores[str(winner_id)] = int(scores.get(str(winner_id), 0)) + bonus
            added_points[str(winner_id)] += bonus

    target = session.room.target_score
    match_winner_ids = [
        player.pk
        for player in players
        if int(scores.get(str(player.pk), 0)) >= target
    ]
    match_loser_ids = [
        player.pk
        for player in players
        if player.pk not in match_winner_ids
    ] if match_winner_ids else []

    session.scores = scores
    session.status = (
        GameSession.Status.FINISHED
        if match_winner_ids
        else GameSession.Status.ROUND_FINISHED
    )
    session.last_round_result = {
        "reason": reason,
        "winner_player_ids": winner_ids,
        "hand_points": {str(key): value for key, value in hand_points.items()},
        "added_penalties": {str(player.pk): 0 for player in players},
        "added_points": added_points,
        "round_bonus_pips": bonus_pips,
        "total_scores": scores,
        "match_loser_player_ids": match_loser_ids,
        "match_winner_player_ids": match_winner_ids,
    }
    clear_turn_clock(session)

    if match_winner_ids:
        session.room.status = GameRoom.Status.FINISHED
        session.room.save(update_fields=["status"])
        record_match_statistics(
            session=session,
            players=players,
            winner_player_ids=match_winner_ids,
            loser_player_ids=match_loser_ids,
        )


def _finish_phone_match(
    *,
    session,
    players,
    winner_player_ids,
    reason,
    added_points,
):
    hands = {key: list(value) for key, value in (session.hands or {}).items()}
    hand_points = _all_hand_points(players=players, hands=hands)
    scores = {str(key): int(value) for key, value in (session.scores or {}).items()}
    winner_ids = list(dict.fromkeys(winner_player_ids))
    loser_ids = [player.pk for player in players if player.pk not in winner_ids]

    session.status = GameSession.Status.FINISHED
    session.last_round_result = {
        "reason": reason,
        "winner_player_ids": winner_ids,
        "hand_points": {str(key): value for key, value in hand_points.items()},
        "added_penalties": {str(player.pk): 0 for player in players},
        "added_points": added_points,
        "round_bonus_pips": 0,
        "total_scores": scores,
        "match_loser_player_ids": loser_ids,
        "match_winner_player_ids": winner_ids,
    }
    clear_turn_clock(session)
    session.room.status = GameRoom.Status.FINISHED
    session.room.save(update_fields=["status"])
    record_match_statistics(
        session=session,
        players=players,
        winner_player_ids=winner_ids,
        loser_player_ids=loser_ids,
    )


def _all_hand_points(*, players, hands):
    return {
        player.pk: _hand_points(hands.get(str(player.pk), []))
        for player in players
    }


def _hand_points(hand):
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

    if _is_phone(session):
        return any(phone_playable_sides(item, table) for item in hand)

    return any(playable_sides(item, table) for item in hand)


def _next_player(players, *, current_player_id):
    ordered = sorted(players, key=lambda player: player.seat_index)

    for index, player in enumerate(ordered):
        if player.pk == current_player_id:
            return ordered[(index + 1) % len(ordered)]

    raise ValidationError({"player_id": "Не удалось определить следующего игрока."})


def game_state_for_player(*, session, player_id):
    return serialize_game_state_for_player(session, player_id)
