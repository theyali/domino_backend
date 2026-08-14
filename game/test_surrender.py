from django.test import TestCase
from rest_framework.exceptions import ValidationError

from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer

from .models import GameSession
from .surrender import surrender_game


class SurrenderGameTests(TestCase):
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
        self.session = GameSession.objects.create(
            room=self.room,
            current_player=self.ali,
            opening_player=self.ali,
            opening_domino_id=10,
            hands={
                str(self.ali.id): [{"id": 10, "left": 6, "right": 6}],
                str(self.john.id): [{"id": 20, "left": 5, "right": 4}],
            },
            boneyard=[],
            table=[],
            scores={str(self.ali.id): 12, str(self.john.id): 18},
        )

    def test_surrender_finishes_match_without_removing_player(self):
        with self.captureOnCommitCallbacks(execute=True):
            session = surrender_game(
                room_id=self.room.id,
                player_id=self.ali.id,
            )

        self.room.refresh_from_db()
        self.ali.refresh_from_db()

        self.assertEqual(session.status, GameSession.Status.FINISHED)
        self.assertEqual(self.room.status, GameRoom.Status.FINISHED)
        self.assertTrue(self.ali.is_active)
        self.assertEqual(session.last_round_result["reason"], "surrender")
        self.assertEqual(
            session.last_round_result["match_loser_player_ids"],
            [self.ali.id],
        )
        self.assertEqual(
            session.last_round_result["match_winner_player_ids"],
            [self.john.id],
        )
        self.assertEqual(
            session.last_round_result["surrendered_player_id"],
            self.ali.id,
        )
        self.assertIsNone(session.turn_started_at)
        self.assertIsNone(session.turn_deadline_at)

    def test_surrender_is_rejected_after_match_finished(self):
        self.session.status = GameSession.Status.FINISHED
        self.session.save(update_fields=["status", "updated_at"])

        with self.assertRaises(ValidationError):
            surrender_game(
                room_id=self.room.id,
                player_id=self.ali.id,
            )
