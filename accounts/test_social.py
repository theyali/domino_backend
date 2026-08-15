from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer

from .models import DirectMessage, Friendship, RoomInvitation, UserProfile


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

    def test_recent_player_can_receive_direct_message(self):
        room = GameRoom.objects.create(
            restaurant=self.restaurant,
            owner_name="Ali",
            max_players=2,
        )
        RoomPlayer.objects.create(
            room=room,
            user=self.ali,
            name="Ali",
            seat_index=0,
            is_owner=True,
        )
        RoomPlayer.objects.create(
            room=room,
            user=self.phone,
            name="Phone",
            seat_index=1,
        )

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
