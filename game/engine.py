import random


VALID_PLAY_SIDES = {"left", "right", "center"}
PHONE_PLAY_SIDES = {"top", "right", "bottom", "left"}


def create_full_set():
    dominoes = []
    domino_id = 0

    for left in range(7):
        for right in range(left, 7):
            dominoes.append(
                {
                    "id": domino_id,
                    "left": left,
                    "right": right,
                }
            )
            domino_id += 1

    return dominoes


def deal_round(players, *, hand_size=7, rng=None, require_double=False):
    if not 2 <= len(players) <= 4:
        raise ValueError("Для домино нужно от 2 до 4 игроков.")

    rng = rng or random.SystemRandom()

    # Для «Телефона» базовая костяшка обязана быть дублем. Перемешиваем
    # повторно, пока хотя бы один дубль не попадёт в руки игроков.
    for _ in range(128):
        deck = create_full_set()
        rng.shuffle(deck)
        hands = {str(player.id): [] for player in players}

        for _ in range(hand_size):
            for player in players:
                if not deck:
                    break
                hands[str(player.id)].append(deck.pop())

        if not require_double or _hands_have_double(hands):
            break
    else:
        raise ValueError("Не удалось раздать стартовый дубль.")

    if require_double:
        opening_player_id, opening_domino_id = choose_phone_opening(hands, players)
    else:
        opening_player_id, opening_domino_id = choose_opening(hands, players)

    return {
        "hands": hands,
        "boneyard": deck,
        "opening_player_id": opening_player_id,
        "opening_domino_id": opening_domino_id,
    }


def _hands_have_double(hands):
    return any(
        domino["left"] == domino["right"]
        for hand in hands.values()
        for domino in hand
    )


def choose_phone_opening(hands, players):
    for double_value in range(6, -1, -1):
        for player in players:
            for domino in hands[str(player.id)]:
                if domino["left"] == double_value and domino["right"] == double_value:
                    return player.id, domino["id"]

    raise ValueError("Для игры «Телефон» в стартовой раздаче нужен дубль.")


def choose_opening(hands, players):
    for double_value in range(6, -1, -1):
        for player in players:
            for domino in hands[str(player.id)]:
                if (
                    domino["left"] == double_value
                    and domino["right"] == double_value
                ):
                    return player.id, domino["id"]

    best_weight = -1
    chosen_player_id = None
    chosen_domino_id = None

    for player in players:
        for domino in hands[str(player.id)]:
            weight = domino["left"] + domino["right"]
            if weight > best_weight:
                best_weight = weight
                chosen_player_id = player.id
                chosen_domino_id = domino["id"]

    if chosen_player_id is None or chosen_domino_id is None:
        raise ValueError("Не удалось определить первого игрока.")

    return chosen_player_id, chosen_domino_id


def find_domino(hand, domino_id):
    for domino in hand:
        if domino["id"] == domino_id:
            return domino
    return None


def playable_sides(domino, table):
    if not table:
        return {"center"}

    left_end = table[0]["left"]
    right_end = table[-1]["right"]
    result = set()

    if domino["left"] == left_end or domino["right"] == left_end:
        result.add("left")

    if domino["left"] == right_end or domino["right"] == right_end:
        result.add("right")

    return result


def orient_domino_for_side(domino, table, side):
    if side not in VALID_PLAY_SIDES:
        raise ValueError("Неизвестная сторона хода.")

    if not table:
        if side != "center":
            raise ValueError("Первая костяшка должна быть положена в центр.")
        return dict(domino)

    if side == "center":
        raise ValueError("После первого хода выберите левую или правую сторону.")

    left = domino["left"]
    right = domino["right"]

    if side == "left":
        target = table[0]["left"]
        if right == target:
            return dict(domino)
        if left == target:
            return {**domino, "left": right, "right": left}
        raise ValueError("Эта костяшка не подходит к левому краю.")

    target = table[-1]["right"]
    if left == target:
        return dict(domino)
    if right == target:
        return {**domino, "left": right, "right": left}
    raise ValueError("Эта костяшка не подходит к правому краю.")


def phone_open_ends(table):
    if not table:
        return {}

    opening = min(table, key=lambda item: int(item.get("move_number", 0) or 0))
    if opening["left"] != opening["right"]:
        raise ValueError("Базовая костяшка «Телефона» должна быть дублем.")

    base_value = opening["left"]
    ends = {side: base_value for side in PHONE_PLAY_SIDES}

    for item in sorted(table, key=lambda value: int(value.get("move_number", 0) or 0)):
        side = item.get("side")
        if side in PHONE_PLAY_SIDES:
            # В телефонной ветке left всегда смотрит к центру, right — наружу.
            ends[side] = item["right"]

    return ends


def phone_playable_sides(domino, table):
    if not table:
        return {"center"}

    ends = phone_open_ends(table)
    return {
        side
        for side, value in ends.items()
        if domino["left"] == value or domino["right"] == value
    }


def orient_phone_domino_for_side(domino, table, side):
    if side not in PHONE_PLAY_SIDES:
        raise ValueError("Выберите одну из четырёх сторон креста.")

    ends = phone_open_ends(table)
    target = ends[side]
    left = domino["left"]
    right = domino["right"]

    if left == target:
        return dict(domino)
    if right == target:
        return {**domino, "left": right, "right": left}
    raise ValueError("Эта костяшка не подходит к выбранному концу креста.")


def phone_open_end_sum(table):
    return sum(phone_open_ends(table).values()) if table else 0
