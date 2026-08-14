from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from restaurants.models import Restaurant
from rooms.models import GameRoom


class RoomApiTests(APITestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(
            name="Mangal Steak House",
            is_active=True,
        )

    def create_room(self, *, max_players=2, password=""):
        response = self.client.post(
            reverse("restaurant-rooms", args=[self.restaurant.id]),
            {
                "owner_name": "Ali",
                "max_players": max_players,
                "password": password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response

    def test_create_room_adds_owner_as_first_player(self):
        response = self.create_room(max_players=4)

        self.assertEqual(response.data["current_players"], 1)
        self.assertEqual(response.data["players"][0]["name"], "Ali")
        self.assertEqual(response.data["players"][0]["seat_index"], 0)
        self.assertTrue(response.data["players"][0]["is_owner"])

    def test_password_is_not_exposed_and_wrong_password_is_rejected(self):
        response = self.create_room(password="1234")
        room_id = response.data["id"]

        self.assertTrue(response.data["is_locked"])
        self.assertNotIn("password", response.data)
        self.assertNotIn("password_hash", response.data)

        wrong = self.client.post(
            reverse("room-join", args=[room_id]),
            {"player_name": "John", "password": "9999"},
            format="json",
        )
        self.assertEqual(wrong.status_code, status.HTTP_400_BAD_REQUEST)

        correct = self.client.post(
            reverse("room-join", args=[room_id]),
            {"player_name": "John", "password": "1234"},
            format="json",
        )
        self.assertEqual(correct.status_code, status.HTTP_201_CREATED)
        self.assertEqual(correct.data["player"]["seat_index"], 1)

    def test_room_rejects_player_when_full(self):
        response = self.create_room(max_players=2)
        room_id = response.data["id"]

        john = self.client.post(
            reverse("room-join", args=[room_id]),
            {"player_name": "John"},
            format="json",
        )
        self.assertEqual(john.status_code, status.HTTP_201_CREATED)

        third = self.client.post(
            reverse("room-join", args=[room_id]),
            {"player_name": "Alex"},
            format="json",
        )
        self.assertEqual(third.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_restaurant_cannot_create_room(self):
        inactive = Restaurant.objects.create(name="Closed", is_active=False)

        response = self.client.post(
            reverse("restaurant-rooms", args=[inactive.id]),
            {"owner_name": "Ali", "max_players": 2},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(GameRoom.objects.count(), 0)
