from django.test import TestCase

from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer

from .models import GameSession
from .state import serialize_game_state_for_player


class RevealedHandsStateTests(TestCase):
    def setUp(self):
        restaurant = Restaurant.objects.create(name="Reveal Test")
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
            opening_domino_id=1,
            hands={
                str(self.ali.id): [{"id": 1, "left": 6, "right": 6}],
                str(self.john.id): [{"id": 2, "left": 3, "right": 5}],
            },
            boneyard=[],
            table=[],
            scores={str(self.ali.id): 0, str(self.john.id): 8},
        )

    def test_active_game_does_not_reveal_other_hands(self):
        state = serialize_game_state_for_player(self.session, self.ali.id)

        self.assertEqual(state["revealed_hands"], {})
        self.assertEqual(state["my_hand"][0]["id"], 1)

    def test_finished_round_reveals_final_hands(self):
        self.session.status = GameSession.Status.ROUND_FINISHED
        self.session.save(update_fields=["status", "updated_at"])

        state = serialize_game_state_for_player(self.session, self.ali.id)

        self.assertEqual(state["revealed_hands"][str(self.ali.id)][0]["id"], 1)
        self.assertEqual(state["revealed_hands"][str(self.john.id)][0]["id"], 2)
        self.assertEqual(
            state["revealed_hands"][str(self.john.id)][0]["game_mode"],
            self.room.game_mode,
        )
