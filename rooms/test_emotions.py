from django.test import SimpleTestCase

from .consumers import RoomLobbyConsumer


class EmotionPayloadValidationTests(SimpleTestCase):
    def test_accepts_supported_emotion_assets(self):
        self.assertEqual(
            RoomLobbyConsumer._validated_emotion_asset(
                "assets/emotions/laugh.png"
            ),
            "assets/emotions/laugh.png",
        )
        self.assertEqual(
            RoomLobbyConsumer._validated_emotion_asset(
                "assets/emotions/animated.gif"
            ),
            "assets/emotions/animated.gif",
        )

    def test_rejects_paths_outside_emotions_directory(self):
        self.assertIsNone(
            RoomLobbyConsumer._validated_emotion_asset(
                "assets/sounds/laugh.png"
            )
        )
        self.assertIsNone(
            RoomLobbyConsumer._validated_emotion_asset(
                "assets/emotions/../sounds/laugh.png"
            )
        )

    def test_rejects_unsupported_extensions(self):
        self.assertIsNone(
            RoomLobbyConsumer._validated_emotion_asset(
                "assets/emotions/script.svg"
            )
        )
