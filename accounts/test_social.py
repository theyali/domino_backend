from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from game.models import GameSession
from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer

from .models import (
    BlockedUser,
    DirectMessage,
    Friendship,
    PushDevice,
    RecentPlayerEncounter,
    RoomInvitation,
    UserProfile,
)


User = get_user_model()


class SocialApiTests(APITestCase):
    def setUp(self):
        self.ali = User.objects.create_user(
            username="ali",
            first_name="Ali",
            password="secret123",
        )
        self.phone = User.objects.create_user(
            username="phone",
            first_name="Phone",
            password="secret123",
        )
        self.third = User.objects.create_user(
            username="third",
            first_name="Third",
            password="secret123",
        )
        for user in (self.ali, self.phone, self.third):
            UserProfile.objects.create(user=user, last_seen_at=timezone.now())

        self.restaurant = Restaurant.objects.create(
            name="Mangal Steak House",
            is_active=True,
        )
        self._authenticate(self.ali)

    def _authenticate(self, user):
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _room_with_two_players(self):
        room = GameRoom.objects.create(
            restaurant=self.restaurant,
            owner_name="Ali",
            max_players=2,
        )
        ali_player = RoomPlayer.objects.create(
            room=room,
            user=self.ali,
            name="Ali",
            seat_index=0,
            is_owner=True,
        )
        phone_player = RoomPlayer.objects.create(
            room=room,
            user=self.phone,
            name="Phone",
            seat_index=1,
        )
        return room, ali_player, phone_player

    def test_friend_request_can_be_accepted(self):
        response = self.client.post(
            reverse("friend-request"),
            {"user_id": self.phone.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        friendship = Friendship.objects.get(
            requester=self.ali,
            addressee=self.phone,
        )

        self._authenticate(self.phone)
        response = self.client.post(reverse("friend-accept", args=[friendship.id]))
        self.assertEqual(response.status_code, 200)
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, Friendship.Status.ACCEPTED)

        overview = self.client.get(reverse("social-overview"))
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.data["friends"][0]["id"], self.ali.id)

    def test_search_users_by_login(self):
        response = self.client.get(reverse("social-user-search"), {"q": "pho"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [self.phone.id])

        own = self.client.get(reverse("social-user-search"), {"q": "ali"})
        self.assertEqual(own.status_code, 200)
        self.assertNotIn(self.ali.id, [item["id"] for item in own.data])

    def test_blocking_user_removes_friendship_and_hides_social_access(self):
        friendship = Friendship.objects.create(
            requester=self.ali,
            addressee=self.phone,
            status=Friendship.Status.ACCEPTED,
            accepted_at=timezone.now(),
        )
        RecentPlayerEncounter.objects.create(user=self.ali, other_user=self.phone)
        RecentPlayerEncounter.objects.create(user=self.phone, other_user=self.ali)

        response = self.client.post(reverse("social-block-user", args=[self.phone.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            BlockedUser.objects.filter(blocker=self.ali, blocked=self.phone).exists()
        )
        self.assertFalse(Friendship.objects.filter(pk=friendship.pk).exists())

        overview = self.client.get(reverse("social-overview"))
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.data["friends"], [])
        self.assertEqual(overview.data["recent_players"], [])

        message = self.client.post(
            reverse("direct-message-thread", args=[self.phone.id]),
            {"body": "blocked"},
            format="json",
        )
        self.assertEqual(message.status_code, 403)

        blocked = self.client.get(reverse("social-blocked"))
        self.assertEqual(blocked.status_code, 200)
        self.assertEqual(blocked.data[0]["id"], self.phone.id)

        unblock = self.client.post(reverse("social-unblock-user", args=[self.phone.id]))
        self.assertEqual(unblock.status_code, 204)
        self.assertFalse(
            BlockedUser.objects.filter(blocker=self.ali, blocked=self.phone).exists()
        )

    def test_notification_settings_and_push_device_registration(self):
        response = self.client.patch(
            reverse("social-notification-settings"),
            {
                "push_notifications_enabled": True,
                "notify_friend_requests": False,
                "notify_room_invites": True,
                "notify_direct_messages": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["notify_friend_requests"])
        self.assertFalse(response.data["notify_direct_messages"])

        device = self.client.post(
            reverse("social-push-devices"),
            {
                "registration_token": "test-device-token",
                "platform": "ios",
            },
            format="json",
        )
        self.assertEqual(device.status_code, 200)
        self.assertTrue(
            PushDevice.objects.filter(
                user=self.ali,
                registration_token="test-device-token",
                is_active=True,
            ).exists()
        )

        remove = self.client.delete(
            reverse("social-push-devices"),
            {"registration_token": "test-device-token"},
            format="json",
        )
        self.assertEqual(remove.status_code, 204)
        self.assertFalse(
            PushDevice.objects.get(registration_token="test-device-token").is_active
        )

    def test_recent_player_can_receive_direct_message(self):
        self._room_with_two_players()

        response = self.client.post(
            reverse("direct-message-thread", args=[self.phone.id]),
            {"body": "Привет!"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(DirectMessage.objects.count(), 1)

        self._authenticate(self.phone)
        thread = self.client.get(
            reverse("direct-message-thread", args=[self.ali.id])
        )
        self.assertEqual(thread.status_code, 200)
        self.assertEqual(thread.data["messages"][0]["body"], "Привет!")
        message = DirectMessage.objects.get()
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_recent_player_remains_after_room_is_deleted(self):
        room, ali_player, _ = self._room_with_two_players()
        GameSession.objects.create(
            room=room,
            current_player=ali_player,
            opening_player=ali_player,
            opening_domino_id=1,
            hands={},
            boneyard=[],
            table=[],
            scores={},
        )

        self.assertTrue(
            RecentPlayerEncounter.objects.filter(
                user=self.ali,
                other_user=self.phone,
            ).exists()
        )

        room.delete()

        overview = self.client.get(reverse("social-overview"))
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(len(overview.data["recent_players"]), 1)
        self.assertEqual(overview.data["recent_players"][0]["id"], self.phone.id)

        response = self.client.post(
            reverse("direct-message-thread", args=[self.phone.id]),
            {"body": "После игры"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_recent_players_returns_only_last_ten(self):
        base_time = timezone.now() - timedelta(minutes=20)
        opponents = []
        for index in range(11):
            opponent = User.objects.create_user(
                username=f"opponent{index}",
                password="secret123",
            )
            UserProfile.objects.create(user=opponent)
            opponents.append(opponent)
            RecentPlayerEncounter.objects.create(
                user=self.ali,
                other_user=opponent,
                last_played_at=base_time + timedelta(minutes=index),
            )

        overview = self.client.get(reverse("social-overview"))
        self.assertEqual(overview.status_code, 200)
        recent = overview.data["recent_players"]
        self.assertEqual(len(recent), 10)
        self.assertEqual(recent[0]["id"], opponents[-1].id)
        self.assertNotIn(opponents[0].id, [item["id"] for item in recent])

    def test_online_player_can_be_invited_and_join_locked_room(self):
        room = GameRoom.objects.create(
            restaurant=self.restaurant,
            owner_name="Ali",
            max_players=2,
        )
        room.set_password("1234")
        room.save(update_fields=["password_hash"])
        RoomPlayer.objects.create(
            room=room,
            user=self.ali,
            name="Ali",
            seat_index=0,
            is_owner=True,
        )

        response = self.client.post(
            reverse("room-invitations", args=[room.id]),
            {"user_ids": [self.phone.id]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["sent"], 1)
        invitation = RoomInvitation.objects.get(
            room=room,
            recipient=self.phone,
        )

        self._authenticate(self.phone)
        response = self.client.post(
            reverse("room-invitation-accept", args=[invitation.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["room"]["id"], room.id)
        self.assertEqual(response.data["restaurant"]["id"], self.restaurant.id)
        self.assertTrue(
            RoomPlayer.objects.filter(
                room=room,
                user=self.phone,
                is_active=True,
            ).exists()
        )
