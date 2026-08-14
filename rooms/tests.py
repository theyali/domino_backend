from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from game.models import GameSession
from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer
from rooms.presence import (
    cleanup_stale_rooms,
    mark_player_offline,
    mark_player_online,
    touch_player,
)


User = get_user_model()


class RoomApiTests(APITestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(
            name="Mangal Steak House",
            is_active=True,
        )
        self._authenticate("ali")

    def _authenticate(self, username):
        user, _ = User.objects.get_or_create(username=username)
        self.client.force_authenticate(user=user)
        return user

    def create_room(self, *, max_players=2, password=""):
        self._authenticate("ali")
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
        self.assertFalse(response.data["players"][0]["is_online"])
        self.assertIsNotNone(response.data["players"][0]["user_id"])

    def test_password_is_not_exposed_and_wrong_password_is_rejected(self):
        response = self.create_room(password="1234")
        room_id = response.data["id"]

        self.assertTrue(response.data["is_locked"])
        self.assertNotIn("password", response.data)
        self.assertNotIn("password_hash", response.data)

        self._authenticate("john")
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
        self.assertIsNotNone(correct.data["player"]["user_id"])

    def test_room_rejects_player_when_full(self):
        response = self.create_room(max_players=2)
        room_id = response.data["id"]

        self._authenticate("john")
        john = self.client.post(
            reverse("room-join", args=[room_id]),
            {"player_name": "John"},
            format="json",
        )
        self.assertEqual(john.status_code, status.HTTP_201_CREATED)

        self._authenticate("alex")
        third = self.client.post(
            reverse("room-join", args=[room_id]),
            {"player_name": "Alex"},
            format="json",
        )
        self.assertEqual(third.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_restaurant_cannot_create_room(self):
        inactive = Restaurant.objects.create(name="Closed", is_active=False)
        self._authenticate("ali")

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

        self._authenticate("john")
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

        self._authenticate("john")
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

    def test_active_game_survives_first_exit_and_table_is_deleted_after_last_exit(self):
        room = GameRoom.objects.create(
            restaurant=self.restaurant,
            owner_name="Ali",
            max_players=2,
            status=GameRoom.Status.PLAYING,
        )
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
        session = GameSession.objects.create(
            room=room,
            current_player=ali,
            opening_player=ali,
            opening_domino_id=10,
            hands={
                str(ali.id): [{"id": 10, "left": 6, "right": 6}],
                str(john.id): [{"id": 20, "left": 5, "right": 6}],
            },
            boneyard=[],
            table=[],
            scores={str(ali.id): 0, str(john.id): 0},
        )

        first_left = self.client.post(
            reverse("room-leave", args=[room.id]),
            {"player_id": ali.id},
            format="json",
        )

        self.assertEqual(first_left.status_code, status.HTTP_200_OK)
        self.assertFalse(first_left.data["room_deleted"])
        self.assertTrue(GameRoom.objects.filter(pk=room.id).exists())
        self.assertTrue(GameSession.objects.filter(pk=session.id).exists())

        session.refresh_from_db()
        room.refresh_from_db()
        ali.refresh_from_db()
        john.refresh_from_db()

        self.assertFalse(ali.is_active)
        self.assertFalse(ali.is_online)
        self.assertTrue(john.is_active)
        self.assertTrue(john.is_owner)
        self.assertEqual(room.current_players, 1)
        self.assertEqual(room.status, GameRoom.Status.FINISHED)
        self.assertEqual(session.status, GameSession.Status.FINISHED)
        self.assertEqual(session.last_round_result["reason"], "player_left")
        self.assertEqual(session.last_round_result["left_player_id"], ali.id)

        last_left = self.client.post(
            reverse("room-leave", args=[room.id]),
            {"player_id": john.id},
            format="json",
        )

        self.assertEqual(last_left.status_code, status.HTTP_200_OK)
        self.assertTrue(last_left.data["room_deleted"])
        self.assertFalse(GameRoom.objects.filter(pk=room.id).exists())
        self.assertFalse(GameSession.objects.filter(pk=session.id).exists())


class RoomPresenceTests(APITestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(
            name="Presence Test",
            is_active=True,
        )
        self.room = GameRoom.objects.create(
            restaurant=self.restaurant,
            owner_name="Ali",
            max_players=2,
        )
        self.player = RoomPlayer.objects.create(
            room=self.room,
            name="Ali",
            seat_index=0,
            is_owner=True,
        )

    def test_presence_can_go_online_touch_and_offline_without_leaving(self):
        mark_player_online(room_id=self.room.id, player_id=self.player.id)
        self.player.refresh_from_db()
        first_seen = self.player.last_seen_at

        self.assertTrue(self.player.is_online)
        self.assertTrue(self.player.is_active)

        touch_player(room_id=self.room.id, player_id=self.player.id)
        self.player.refresh_from_db()
        self.assertGreaterEqual(self.player.last_seen_at, first_seen)
        self.assertTrue(self.player.is_online)

        mark_player_offline(room_id=self.room.id, player_id=self.player.id)
        self.player.refresh_from_db()
        self.assertFalse(self.player.is_online)
        self.assertTrue(self.player.is_active)

    def test_cleanup_keeps_recent_offline_room_for_reconnect(self):
        self.player.is_online = False
        self.player.last_seen_at = timezone.now() - timedelta(minutes=5)
        self.player.save(update_fields=["is_online", "last_seen_at"])

        deleted = cleanup_stale_rooms(minutes=30)

        self.assertNotIn(self.room.id, deleted)
        self.assertTrue(GameRoom.objects.filter(pk=self.room.id).exists())

    def test_cleanup_deletes_room_after_reconnect_timeout(self):
        self.player.is_online = False
        self.player.last_seen_at = timezone.now() - timedelta(minutes=31)
        self.player.save(update_fields=["is_online", "last_seen_at"])

        deleted = cleanup_stale_rooms(minutes=30)

        self.assertIn(self.room.id, deleted)
        self.assertFalse(GameRoom.objects.filter(pk=self.room.id).exists())
