from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer

from .models import GameSession
from .turn_clock import TURN_SECONDS
from .turn_timeout import process_expired_turn


class TurnTimerTests(TestCase):
    def setUp(self):
        restaurant = Restaurant.objects.create(name="Timer Test")
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

    def _create_session(self, *, hand, boneyard=None, table=None):
        expired_at = timezone.now() - timedelta(seconds=1)
        return GameSession.objects.create(
            room=self.room,
            current_player=self.ali,
            opening_player=self.ali,
            opening_domino_id=10,
            hands={
                str(self.ali.id): hand,
                str(self.john.id): [
                    {"id": 20, "left": 3, "right": 4},
                    {"id": 21, "left": 4, "right": 5},
                ],
            },
            boneyard=boneyard or [],
            table=table or [],
            scores={str(self.ali.id): 0, str(self.john.id): 0},
            turn_started_at=expired_at - timedelta(seconds=TURN_SECONDS),
            turn_deadline_at=expired_at,
        )

    def test_timeout_automatically_plays_first_legal_domino(self):
        session = self._create_session(
            hand=[
                {"id": 11, "left": 6, "right": 2},
                {"id": 12, "left": 1, "right": 3},
            ],
            table=[
                {
                    "id": 99,
                    "left": 6,
                    "right": 6,
                    "played_by_player_id": self.john.id,
                    "side": "center",
                    "move_number": 1,
                }
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            processed = process_expired_turn(room_id=self.room.id)

        self.assertTrue(processed)
        session.refresh_from_db()
        self.assertEqual(session.current_player_id, self.john.id)
        self.assertEqual(session.version, 2)
        self.assertEqual(len(session.hands[str(self.ali.id)]), 1)
        self.assertEqual(session.hands[str(self.ali.id)][0]["id"], 12)
        self.assertEqual(len(session.table), 2)
        self.assertEqual(session.table[0]["id"], 11)
        self.assertGreater(session.turn_deadline_at, timezone.now())

    def test_timeout_draws_one_domino_and_gives_same_player_new_time(self):
        session = self._create_session(
            hand=[{"id": 11, "left": 1, "right": 2}],
            boneyard=[{"id": 30, "left": 3, "right": 5}],
            table=[
                {
                    "id": 99,
                    "left": 6,
                    "right": 6,
                    "played_by_player_id": self.john.id,
                    "side": "center",
                    "move_number": 1,
                }
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            processed = process_expired_turn(room_id=self.room.id)

        self.assertTrue(processed)
        session.refresh_from_db()
        self.assertEqual(session.current_player_id, self.ali.id)
        self.assertEqual(session.boneyard, [])
        self.assertEqual(len(session.hands[str(self.ali.id)]), 2)
        self.assertEqual(session.hands[str(self.ali.id)][-1]["id"], 30)
        self.assertGreater(session.turn_deadline_at, timezone.now())

        self.assertFalse(process_expired_turn(room_id=self.room.id))

    def test_timeout_passes_when_no_move_and_boneyard_is_empty(self):
        session = self._create_session(
            hand=[{"id": 11, "left": 1, "right": 2}],
            table=[
                {
                    "id": 99,
                    "left": 6,
                    "right": 6,
                    "played_by_player_id": self.john.id,
                    "side": "center",
                    "move_number": 1,
                }
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            processed = process_expired_turn(room_id=self.room.id)

        self.assertTrue(processed)
        session.refresh_from_db()
        self.assertEqual(session.current_player_id, self.john.id)
        self.assertEqual(session.consecutive_passes, 1)
        self.assertEqual(session.version, 2)
        self.assertGreater(session.turn_deadline_at, timezone.now())

    def test_timeout_plays_required_opening_domino(self):
        session = self._create_session(
            hand=[
                {"id": 10, "left": 6, "right": 6},
                {"id": 11, "left": 1, "right": 2},
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            processed = process_expired_turn(room_id=self.room.id)

        self.assertTrue(processed)
        session.refresh_from_db()
        self.assertEqual(session.table[0]["id"], 10)
        self.assertEqual(session.table[0]["side"], "center")
        self.assertEqual(session.current_player_id, self.john.id)
