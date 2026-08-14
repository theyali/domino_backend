from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from restaurants.models import Restaurant

from .models import GameRoom, RoomPlayer
from .presence import (
    mark_player_offline,
    mark_player_online,
    mark_stale_players_offline,
    touch_player,
)


class ReconnectSafePresenceTests(TestCase):
    def setUp(self):
        restaurant = Restaurant.objects.create(
            name="Presence reconnect test",
            is_active=True,
        )
        self.room = GameRoom.objects.create(
            restaurant=restaurant,
            owner_name="Ali",
            max_players=2,
        )
        self.player = RoomPlayer.objects.create(
            room=self.room,
            name="Ali",
            seat_index=0,
            is_owner=True,
        )

    def test_old_disconnect_cannot_mark_new_connection_offline(self):
        mark_player_online(
            room_id=self.room.id,
            player_id=self.player.id,
            connection_token="old-connection",
        )
        mark_player_online(
            room_id=self.room.id,
            player_id=self.player.id,
            connection_token="new-connection",
        )

        updated = mark_player_offline(
            room_id=self.room.id,
            player_id=self.player.id,
            connection_token="old-connection",
        )

        self.player.refresh_from_db()
        self.assertEqual(updated, 0)
        self.assertTrue(self.player.is_online)
        self.assertEqual(
            self.player.presence_connection_token,
            "new-connection",
        )

    def test_current_disconnect_marks_player_offline(self):
        mark_player_online(
            room_id=self.room.id,
            player_id=self.player.id,
            connection_token="current-connection",
        )

        updated = mark_player_offline(
            room_id=self.room.id,
            player_id=self.player.id,
            connection_token="current-connection",
        )

        self.player.refresh_from_db()
        self.assertEqual(updated, 1)
        self.assertFalse(self.player.is_online)
        self.assertEqual(self.player.presence_connection_token, "")
        self.assertTrue(self.player.is_active)

    def test_old_heartbeat_cannot_take_over_new_connection(self):
        mark_player_online(
            room_id=self.room.id,
            player_id=self.player.id,
            connection_token="new-connection",
        )
        before = self.player.last_seen_at

        updated = touch_player(
            room_id=self.room.id,
            player_id=self.player.id,
            connection_token="old-connection",
        )

        self.player.refresh_from_db()
        self.assertEqual(updated, 0)
        self.assertEqual(self.player.presence_connection_token, "new-connection")
        self.assertEqual(self.player.last_seen_at, before)

    def test_stale_online_player_is_marked_offline(self):
        self.player.is_online = True
        self.player.presence_connection_token = "stale-connection"
        self.player.last_seen_at = timezone.now() - timedelta(seconds=40)
        self.player.save(
            update_fields=[
                "is_online",
                "presence_connection_token",
                "last_seen_at",
            ]
        )

        updated = mark_stale_players_offline(
            room_id=self.room.id,
            seconds=35,
        )

        self.player.refresh_from_db()
        self.assertEqual(updated, 1)
        self.assertFalse(self.player.is_online)
        self.assertEqual(self.player.presence_connection_token, "")
