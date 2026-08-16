from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from restaurants.models import Restaurant
from rooms.models import RoomPlayer


User = get_user_model()


class RoomBotTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bot_host")
        self.restaurant = Restaurant.objects.create(name="Bot Test", is_active=True)
        self.client.force_authenticate(self.user)

    def test_room_can_reserve_mixed_bot_and_human_seats(self):
        response = self.client.post(
            reverse("restaurant-rooms", args=[self.restaurant.id]),
            {
                "max_players": 4,
                "game_mode": "phone",
                "target_score": 72,
                "bot_count": 2,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["current_players"], 3)
        self.assertEqual(response.data["bot_count"], 2)
        bots = [item for item in response.data["players"] if item["is_bot"]]
        self.assertEqual(len(bots), 2)
        self.assertTrue(all(item["user_id"] is None for item in bots))
        self.assertTrue(all(item["is_online"] for item in bots))

    def test_classic_room_can_be_host_vs_bot(self):
        response = self.client.post(
            reverse("restaurant-rooms", args=[self.restaurant.id]),
            {"max_players": 2, "game_mode": "101", "bot_count": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_full"])
        self.assertEqual(response.data["bot_count"], 1)

    def test_bot_count_cannot_take_host_seat(self):
        response = self.client.post(
            reverse("restaurant-rooms", args=[self.restaurant.id]),
            {
                "max_players": 4,
                "game_mode": "phone",
                "target_score": 72,
                "bot_count": 4,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_bots_never_become_owner_when_host_leaves(self):
        response = self.client.post(
            reverse("restaurant-rooms", args=[self.restaurant.id]),
            {"max_players": 2, "game_mode": "101", "bot_count": 1},
            format="json",
        )
        room_id = response.data["id"]
        host_id = next(item["id"] for item in response.data["players"] if not item["is_bot"])
        left = self.client.post(
            reverse("room-leave", args=[room_id]),
            {"player_id": host_id},
            format="json",
        )
        self.assertEqual(left.status_code, 200)
        self.assertTrue(left.data["room_deleted"])
        self.assertFalse(RoomPlayer.objects.filter(room_id=room_id).exists())
