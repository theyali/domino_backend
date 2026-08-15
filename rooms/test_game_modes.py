from django.test import SimpleTestCase

from .models import GameRoom
from .serializers import GameRoomCreateSerializer


class GameRoomModeSerializerTests(SimpleTestCase):
    def test_101_forces_two_players_and_target_101(self):
        serializer = GameRoomCreateSerializer(
            data={
                "max_players": 2,
                "game_mode": GameRoom.GameMode.CLASSIC_101,
                "target_score": 72,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["target_score"], 101)

    def test_101_rejects_more_than_two_players(self):
        serializer = GameRoomCreateSerializer(
            data={
                "max_players": 3,
                "game_mode": GameRoom.GameMode.CLASSIC_101,
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("max_players", serializer.errors)

    def test_phone_accepts_four_players_and_custom_target(self):
        serializer = GameRoomCreateSerializer(
            data={
                "max_players": 4,
                "game_mode": GameRoom.GameMode.PHONE,
                "target_score": 125,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["target_score"], 125)
