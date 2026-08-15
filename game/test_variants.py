from django.test import TestCase

from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer

from .engine import phone_open_end_sum, phone_open_ends, phone_playable_sides
from .models import GameSession
from .services import play_domino


class DominoVariantTests(TestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(name="Rules Test")

    def _players(self, room):
        ali = RoomPlayer.objects.create(
            room=room,
            name="Ali",
            seat_index=0,
            is_owner=True,
        )
        john = RoomPlayer.objects.create(
            room=room,
            name="John",
            seat_index=1,
        )
        return ali, john

    def test_101_records_exact_remaining_pips_even_below_13(self):
        room = GameRoom.objects.create(
            restaurant=self.restaurant,
            owner_name="Ali",
            max_players=2,
            game_mode=GameRoom.GameMode.CLASSIC_101,
            target_score=101,
            status=GameRoom.Status.PLAYING,
        )
        ali, john = self._players(room)
        session = GameSession.objects.create(
            room=room,
            current_player=ali,
            opening_player=ali,
            opening_domino_id=10,
            hands={
                str(ali.id): [{"id": 10, "left": 6, "right": 2}],
                str(john.id): [{"id": 20, "left": 1, "right": 1}],
            },
            boneyard=[],
            table=[
                {
                    "id": 99,
                    "left": 6,
                    "right": 6,
                    "played_by_player_id": john.id,
                    "side": "center",
                    "move_number": 1,
                }
            ],
            scores={str(ali.id): 0, str(john.id): 0},
        )

        with self.captureOnCommitCallbacks(execute=True):
            session = play_domino(
                room_id=room.id,
                player_id=ali.id,
                domino_id=10,
                side="right",
            )

        self.assertEqual(session.status, GameSession.Status.ROUND_FINISHED)
        self.assertEqual(session.scores[str(ali.id)], 0)
        self.assertEqual(session.scores[str(john.id)], 2)
        self.assertEqual(session.last_round_result["added_penalties"][str(john.id)], 2)

    def test_101_blank_double_is_zero_pips_not_special_25(self):
        room = GameRoom.objects.create(
            restaurant=self.restaurant,
            owner_name="Ali",
            max_players=2,
            game_mode=GameRoom.GameMode.CLASSIC_101,
            status=GameRoom.Status.PLAYING,
        )
        ali, john = self._players(room)
        session = GameSession.objects.create(
            room=room,
            current_player=ali,
            opening_player=ali,
            opening_domino_id=10,
            hands={
                str(ali.id): [{"id": 10, "left": 6, "right": 2}],
                str(john.id): [{"id": 20, "left": 0, "right": 0}],
            },
            boneyard=[],
            table=[
                {
                    "id": 99,
                    "left": 6,
                    "right": 6,
                    "played_by_player_id": john.id,
                    "side": "center",
                    "move_number": 1,
                }
            ],
            scores={str(ali.id): 0, str(john.id): 0},
        )

        with self.captureOnCommitCallbacks(execute=True):
            session = play_domino(
                room_id=room.id,
                player_id=ali.id,
                domino_id=10,
                side="right",
            )

        self.assertEqual(session.scores[str(john.id)], 0)

    def test_phone_has_four_open_ends_from_base_double(self):
        table = [
            {
                "id": 10,
                "left": 5,
                "right": 5,
                "side": "center",
                "move_number": 1,
            }
        ]

        self.assertEqual(
            phone_open_ends(table),
            {"top": 5, "right": 5, "bottom": 5, "left": 5},
        )
        self.assertEqual(phone_open_end_sum(table), 20)
        self.assertEqual(
            phone_playable_sides({"id": 11, "left": 2, "right": 5}, table),
            {"top", "right", "bottom", "left"},
        )

    def test_phone_awards_open_end_sum_divided_by_five(self):
        room = GameRoom.objects.create(
            restaurant=self.restaurant,
            owner_name="Ali",
            max_players=2,
            game_mode=GameRoom.GameMode.PHONE,
            target_score=72,
            status=GameRoom.Status.PLAYING,
        )
        ali, john = self._players(room)
        session = GameSession.objects.create(
            room=room,
            current_player=ali,
            opening_player=ali,
            opening_domino_id=10,
            hands={
                str(ali.id): [
                    {"id": 10, "left": 5, "right": 5},
                    {"id": 11, "left": 5, "right": 1},
                ],
                str(john.id): [
                    {"id": 20, "left": 5, "right": 0},
                    {"id": 21, "left": 4, "right": 4},
                ],
            },
            boneyard=[],
            table=[],
            scores={str(ali.id): 0, str(john.id): 0},
        )

        with self.captureOnCommitCallbacks(execute=True):
            session = play_domino(
                room_id=room.id,
                player_id=ali.id,
                domino_id=10,
                side="center",
            )

        # 5 + 5 + 5 + 5 = 20; 20 / 5 = 4 активных очка.
        self.assertEqual(session.scores[str(ali.id)], 4)
        self.assertEqual(session.current_player_id, john.id)

        with self.captureOnCommitCallbacks(execute=True):
            session = play_domino(
                room_id=room.id,
                player_id=john.id,
                domino_id=20,
                side="top",
            )

        # После 5/0 сверху открытые концы: 0 + 5 + 5 + 5 = 15 => 3.
        self.assertEqual(session.scores[str(john.id)], 3)
        self.assertEqual(session.table[-1]["side"], "top")
        self.assertEqual(phone_open_end_sum(session.table), 15)
