import random

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer

from .engine import (
    create_full_set,
    deal_round,
    orient_domino_for_side,
    playable_sides,
)
from .models import GameSession
from .services import (
    draw_domino,
    pass_turn,
    play_domino,
    start_game,
    start_next_round,
)


class GameEngineTests(TestCase):
    def test_full_set_has_28_unique_dominoes(self):
        dominoes = create_full_set()
        self.assertEqual(len(dominoes), 28)
        self.assertEqual(len({item["id"] for item in dominoes}), 28)

    def test_two_players_receive_seven_dominoes(self):
        restaurant = Restaurant.objects.create(name="Test")
        room = GameRoom.objects.create(
            restaurant=restaurant,
            owner_name="Ali",
            max_players=2,
        )
        players = [
            RoomPlayer.objects.create(
                room=room,
                name="Ali",
                seat_index=0,
                is_owner=True,
            ),
            RoomPlayer.objects.create(
                room=room,
                name="John",
                seat_index=1,
            ),
        ]

        result = deal_round(players, rng=random.Random(42))

        self.assertEqual(len(result["hands"][str(players[0].id)]), 7)
        self.assertEqual(len(result["hands"][str(players[1].id)]), 7)
        self.assertEqual(len(result["boneyard"]), 14)

    def test_domino_is_flipped_for_right_edge(self):
        table = [{"id": 1, "left": 6, "right": 5}]
        domino = {"id": 2, "left": 2, "right": 5}

        self.assertEqual(playable_sides(domino, table), {"right"})
        self.assertEqual(
            orient_domino_for_side(domino, table, "right"),
            {"id": 2, "left": 5, "right": 2},
        )

    def test_domino_can_match_both_ends(self):
        table = [{"id": 1, "left": 5, "right": 5}]
        domino = {"id": 2, "left": 2, "right": 5}

        self.assertEqual(playable_sides(domino, table), {"left", "right"})


class StartGameTests(TestCase):
    def test_owner_can_start_full_room(self):
        restaurant = Restaurant.objects.create(name="Test")
        room = GameRoom.objects.create(
            restaurant=restaurant,
            owner_name="Ali",
            max_players=2,
        )
        owner = RoomPlayer.objects.create(
            room=room,
            name="Ali",
            seat_index=0,
            is_owner=True,
        )
        RoomPlayer.objects.create(
            room=room,
            name="John",
            seat_index=1,
        )

        session = start_game(room_id=room.id, player_id=owner.id)

        room.refresh_from_db()
        self.assertEqual(room.status, GameRoom.Status.PLAYING)
        self.assertEqual(session.room_id, room.id)
        self.assertEqual(len(session.hands[str(owner.id)]), 7)


class GameActionTests(TestCase):
    def setUp(self):
        restaurant = Restaurant.objects.create(name="Test")
        self.room = GameRoom.objects.create(
            restaurant=restaurant,
            owner_name="Ali",
            max_players=2,
            status=GameRoom.Status.PLAYING,
        )
        self.ali = RoomPlayer.objects.create(
            room=self.room,
            name="Ali",
            seat_index=0,
            is_owner=True,
        )
        self.john = RoomPlayer.objects.create(
            room=self.room,
            name="John",
            seat_index=1,
        )

    def _create_session(self):
        return GameSession.objects.create(
            room=self.room,
            current_player=self.ali,
            opening_player=self.ali,
            opening_domino_id=10,
            hands={
                str(self.ali.id): [
                    {"id": 10, "left": 6, "right": 6},
                    {"id": 11, "left": 2, "right": 5},
                ],
                str(self.john.id): [
                    {"id": 20, "left": 5, "right": 6},
                    {"id": 21, "left": 1, "right": 3},
                ],
            },
            boneyard=[],
            table=[],
            scores={str(self.ali.id): 0, str(self.john.id): 0},
        )

    def test_opening_domino_moves_from_hand_to_table_and_turn_changes(self):
        session = self._create_session()

        with self.captureOnCommitCallbacks(execute=True):
            session = play_domino(
                room_id=self.room.id,
                player_id=self.ali.id,
                domino_id=10,
                side="center",
            )

        self.assertEqual(session.current_player_id, self.john.id)
        self.assertEqual(session.version, 2)
        self.assertEqual(len(session.hands[str(self.ali.id)]), 1)
        self.assertEqual(len(session.table), 1)
        self.assertEqual(session.table[0]["id"], 10)
        self.assertEqual(session.table[0]["played_by_player_id"], self.ali.id)

    def test_server_rejects_move_from_wrong_player(self):
        self._create_session()

        with self.assertRaises(ValidationError):
            play_domino(
                room_id=self.room.id,
                player_id=self.john.id,
                domino_id=20,
                side="center",
            )

    def test_server_rejects_wrong_opening_domino(self):
        self._create_session()

        with self.assertRaises(ValidationError):
            play_domino(
                room_id=self.room.id,
                player_id=self.ali.id,
                domino_id=11,
                side="center",
            )

    def test_second_move_is_oriented_and_added_to_chain(self):
        session = self._create_session()
        session.table = [
            {
                "id": 10,
                "left": 6,
                "right": 6,
                "played_by_player_id": self.ali.id,
                "side": "center",
                "move_number": 1,
            }
        ]
        session.hands[str(self.ali.id)] = [{"id": 11, "left": 2, "right": 5}]
        session.current_player = self.john
        session.version = 2
        session.save(
            update_fields=["table", "hands", "current_player", "version", "updated_at"]
        )

        with self.captureOnCommitCallbacks(execute=True):
            session = play_domino(
                room_id=self.room.id,
                player_id=self.john.id,
                domino_id=20,
                side="right",
            )

        self.assertEqual(session.current_player_id, self.ali.id)
        self.assertEqual(session.table[-1]["left"], 6)
        self.assertEqual(session.table[-1]["right"], 5)
        self.assertEqual(session.hands[str(self.john.id)][0]["id"], 21)

    def test_draw_adds_one_domino_and_keeps_current_player(self):
        session = self._create_session()
        session.table = [
            {
                "id": 10,
                "left": 6,
                "right": 6,
                "played_by_player_id": self.john.id,
                "side": "center",
                "move_number": 1,
            }
        ]
        session.hands[str(self.ali.id)] = [{"id": 11, "left": 2, "right": 5}]
        session.boneyard = [{"id": 30, "left": 1, "right": 4}]
        session.save(update_fields=["table", "hands", "boneyard", "updated_at"])

        with self.captureOnCommitCallbacks(execute=True):
            session = draw_domino(room_id=self.room.id, player_id=self.ali.id)

        self.assertEqual(session.current_player_id, self.ali.id)
        self.assertEqual(session.version, 2)
        self.assertEqual(len(session.boneyard), 0)
        self.assertEqual(len(session.hands[str(self.ali.id)]), 2)
        self.assertEqual(session.hands[str(self.ali.id)][-1]["id"], 30)
        self.assertEqual(session.consecutive_passes, 0)

    def test_draw_is_rejected_when_player_already_has_move(self):
        session = self._create_session()
        session.table = [
            {
                "id": 99,
                "left": 5,
                "right": 5,
                "played_by_player_id": self.john.id,
                "side": "center",
                "move_number": 1,
            }
        ]
        session.boneyard = [{"id": 30, "left": 1, "right": 4}]
        session.save(update_fields=["table", "boneyard", "updated_at"])

        with self.assertRaises(ValidationError):
            draw_domino(room_id=self.room.id, player_id=self.ali.id)

    def test_pass_changes_turn_when_boneyard_is_empty_and_no_move_exists(self):
        session = self._create_session()
        session.table = [
            {
                "id": 99,
                "left": 6,
                "right": 6,
                "played_by_player_id": self.john.id,
                "side": "center",
                "move_number": 1,
            }
        ]
        session.hands[str(self.ali.id)] = [{"id": 11, "left": 2, "right": 5}]
        session.boneyard = []
        session.save(update_fields=["table", "hands", "boneyard", "updated_at"])

        with self.captureOnCommitCallbacks(execute=True):
            session = pass_turn(room_id=self.room.id, player_id=self.ali.id)

        self.assertEqual(session.current_player_id, self.john.id)
        self.assertEqual(session.version, 2)
        self.assertEqual(session.consecutive_passes, 1)

    def test_pass_is_rejected_while_boneyard_has_dominoes(self):
        session = self._create_session()
        session.table = [
            {
                "id": 99,
                "left": 6,
                "right": 6,
                "played_by_player_id": self.john.id,
                "side": "center",
                "move_number": 1,
            }
        ]
        session.hands[str(self.ali.id)] = [{"id": 11, "left": 2, "right": 5}]
        session.boneyard = [{"id": 30, "left": 1, "right": 4}]
        session.save(update_fields=["table", "hands", "boneyard", "updated_at"])

        with self.assertRaises(ValidationError):
            pass_turn(room_id=self.room.id, player_id=self.ali.id)

    def test_last_domino_finishes_round_and_records_penalty(self):
        session = self._create_session()
        session.table = [
            {
                "id": 99,
                "left": 6,
                "right": 6,
                "played_by_player_id": self.john.id,
                "side": "center",
                "move_number": 1,
            }
        ]
        session.hands = {
            str(self.ali.id): [{"id": 11, "left": 6, "right": 2}],
            str(self.john.id): [
                {"id": 20, "left": 6, "right": 6},
                {"id": 21, "left": 5, "right": 5},
            ],
        }
        session.current_player = self.ali
        session.save(update_fields=["table", "hands", "current_player", "updated_at"])

        with self.captureOnCommitCallbacks(execute=True):
            session = play_domino(
                room_id=self.room.id,
                player_id=self.ali.id,
                domino_id=11,
                side="right",
            )

        self.assertEqual(session.status, GameSession.Status.ROUND_FINISHED)
        self.assertEqual(session.scores[str(self.john.id)], 22)
        self.assertEqual(session.last_round_result["reason"], "domino")
        self.assertEqual(
            session.last_round_result["winner_player_ids"],
            [self.ali.id],
        )

    def test_reaching_101_finishes_match(self):
        session = self._create_session()
        session.table = [
            {
                "id": 99,
                "left": 6,
                "right": 6,
                "played_by_player_id": self.john.id,
                "side": "center",
                "move_number": 1,
            }
        ]
        session.hands = {
            str(self.ali.id): [{"id": 11, "left": 6, "right": 2}],
            str(self.john.id): [
                {"id": 20, "left": 6, "right": 6},
                {"id": 21, "left": 5, "right": 5},
            ],
        }
        session.scores = {str(self.ali.id): 0, str(self.john.id): 90}
        session.current_player = self.ali
        session.save(
            update_fields=["table", "hands", "scores", "current_player", "updated_at"]
        )

        with self.captureOnCommitCallbacks(execute=True):
            session = play_domino(
                room_id=self.room.id,
                player_id=self.ali.id,
                domino_id=11,
                side="right",
            )

        self.room.refresh_from_db()
        self.assertEqual(session.status, GameSession.Status.FINISHED)
        self.assertEqual(self.room.status, GameRoom.Status.FINISHED)
        self.assertGreaterEqual(session.scores[str(self.john.id)], 101)
        self.assertIn(
            self.john.id,
            session.last_round_result["match_loser_player_ids"],
        )

    def test_consecutive_passes_finish_fish_round(self):
        session = self._create_session()
        session.table = [
            {
                "id": 99,
                "left": 6,
                "right": 6,
                "played_by_player_id": self.john.id,
                "side": "center",
                "move_number": 1,
            }
        ]
        session.hands = {
            str(self.ali.id): [{"id": 11, "left": 1, "right": 2}],
            str(self.john.id): [{"id": 21, "left": 3, "right": 4}],
        }
        session.boneyard = []
        session.current_player = self.ali
        session.save(
            update_fields=["table", "hands", "boneyard", "current_player", "updated_at"]
        )

        with self.captureOnCommitCallbacks(execute=True):
            session = pass_turn(room_id=self.room.id, player_id=self.ali.id)
        self.assertEqual(session.status, GameSession.Status.ACTIVE)
        self.assertEqual(session.current_player_id, self.john.id)

        with self.captureOnCommitCallbacks(execute=True):
            session = pass_turn(room_id=self.room.id, player_id=self.john.id)

        self.assertEqual(session.status, GameSession.Status.ROUND_FINISHED)
        self.assertEqual(session.last_round_result["reason"], "fish")
        self.assertEqual(
            session.last_round_result["winner_player_ids"],
            [self.ali.id],
        )

    def test_owner_can_start_next_round_and_scores_are_preserved(self):
        session = self._create_session()
        session.status = GameSession.Status.ROUND_FINISHED
        session.scores = {str(self.ali.id): 0, str(self.john.id): 22}
        session.last_round_result = {"reason": "domino"}
        session.save(update_fields=["status", "scores", "last_round_result", "updated_at"])

        with self.captureOnCommitCallbacks(execute=True):
            session = start_next_round(
                room_id=self.room.id,
                player_id=self.ali.id,
            )

        self.assertEqual(session.status, GameSession.Status.ACTIVE)
        self.assertEqual(session.round_number, 2)
        self.assertEqual(session.scores[str(self.john.id)], 22)
        self.assertEqual(len(session.hands[str(self.ali.id)]), 7)
        self.assertEqual(len(session.hands[str(self.john.id)]), 7)
        self.assertEqual(len(session.boneyard), 14)
        self.assertEqual(session.table, [])
        self.assertEqual(session.last_round_result, {})
