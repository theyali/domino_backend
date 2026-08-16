from django.contrib.auth import get_user_model
from django.test import TestCase

from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer

from .bots import process_bot_turns
from .models import GameSession


User = get_user_model()


class ServerBotTurnTests(TestCase):
    def test_bot_uses_same_authoritative_play_service(self):
        user = User.objects.create_user(username="human")
        restaurant = Restaurant.objects.create(name="Bot Engine", is_active=True)
        room = GameRoom.objects.create(
            restaurant=restaurant,
            owner_name="Human",
            max_players=2,
            status=GameRoom.Status.PLAYING,
        )
        human = RoomPlayer.objects.create(
            room=room, user=user, name="Human", seat_index=0, is_owner=True
        )
        bot = RoomPlayer.objects.create(
            room=room,
            name="Bot 1",
            seat_index=1,
            is_bot=True,
            is_online=True,
        )
        session = GameSession.objects.create(
            room=room,
            current_player=bot,
            opening_player=bot,
            opening_domino_id=27,
            hands={
                str(human.id): [{"id": 20, "left": 5, "right": 5}],
                str(bot.id): [{"id": 27, "left": 6, "right": 6}],
            },
            boneyard=[],
            table=[],
            scores={str(human.id): 0, str(bot.id): 0},
        )

        actions = process_bot_turns(room_id=room.id)
        self.assertEqual(actions, 1)
        session.refresh_from_db()
        self.assertEqual(len(session.table), 1)
        self.assertEqual(session.table[0]["played_by_player_id"], bot.id)
        self.assertNotEqual(session.status, GameSession.Status.ACTIVE)
