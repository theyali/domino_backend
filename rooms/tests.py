from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer


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
        self.assertTrue(response.data["players"][0]["is_active"])

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

    def test_owner_leave_transfers_ownership_when_player_remains(self):
        created = self.create_room(max_players=2)
        room_id = created.data["id"]
        owner_id = created.data["players"][0]["id"]

        joined = self.client.post(
            reverse("room-join", args=[room_id]),
            {"player_name": "John"},
            format="json",
        )
        self.assertEqual(joined.status_code, status.HTTP_201_CREATED)
        john_id = joined.data["player"]["id"]

        left = self.client.post(
            reverse("room-leave", args=[room_id]),
            {"player_id": owner_id},
            format="json",
        )

        self.assertEqual(left.status_code, status.HTTP_200_OK)
        self.assertFalse(left.data["room_deleted"])

        room = GameRoom.objects.get(pk=room_id)
        john = RoomPlayer.objects.get(pk=john_id)
        self.assertEqual(room.owner_name, "John")
        self.assertTrue(john.is_owner)
        self.assertEqual(room.current_players, 1)

    def test_room_is_deleted_only_after_last_waiting_player_leaves(self):
        created = self.create_room(max_players=2)
        room_id = created.data["id"]
        owner_id = created.data["players"][0]["id"]

        joined = self.client.post(
            reverse("room-join", args=[room_id]),
            {"player_name": "John"},
            format="json",
        )
        john_id = joined.data["player"]["id"]

        self.client.post(
            reverse("room-leave", args=[room_id]),
            {"player_id": owner_id},
            format="json",
        )
        self.assertTrue(GameRoom.objects.filter(pk=room_id).exists())

        last_left = self.client.post(
            reverse("room-leave", args=[room_id]),
            {"player_id": john_id},
            format="json",
        )

        self.assertEqual(last_left.status_code, status.HTTP_200_OK)
        self.assertTrue(last_left.data["room_deleted"])
        self.assertFalse(GameRoom.objects.filter(pk=room_id).exists())
