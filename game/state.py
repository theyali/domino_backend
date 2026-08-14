def serialize_game_state_for_player(session, player_id):
    room = session.room
    players = list(room.players.all())
    hands = session.hands or {}
    scores = session.scores or {}
    my_hand = hands.get(str(player_id), [])

    return {
        "game_id": session.pk,
        "room_id": room.pk,
        "status": session.status,
        "round_number": session.round_number,
        "version": session.version,
        "current_player_id": session.current_player_id,
        "opening_player_id": session.opening_player_id,
        "opening_domino_id": session.opening_domino_id,
        "boneyard_count": len(session.boneyard or []),
        "table": session.table or [],
        "my_player_id": player_id,
        "my_hand": my_hand,
        "round_result": session.last_round_result or None,
        "players": [
            {
                "id": player.id,
                "name": player.name,
                "seat_index": player.seat_index,
                "is_owner": player.is_owner,
                "is_active": player.is_active,
                "is_online": player.is_online,
                "last_seen_at": (
                    player.last_seen_at.isoformat()
                    if player.last_seen_at is not None
                    else None
                ),
                "score": int(scores.get(str(player.id), 0)),
                "domino_count": len(hands.get(str(player.id), [])),
            }
            for player in players
        ],
    }
