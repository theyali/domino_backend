from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Friendship


User = get_user_model()


class FriendRequestActionTests(APITestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username="friend_sender")
        self.recipient = User.objects.create_user(username="friend_recipient")

    def test_outgoing_request_can_be_cancelled(self):
        friendship = Friendship.objects.create(
            requester=self.sender, addressee=self.recipient
        )
        self.client.force_authenticate(self.sender)
        overview = self.client.get(reverse("social-overview"))
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.data["outgoing_requests"][0]["id"], friendship.id)

        response = self.client.post(reverse("friend-cancel", args=[friendship.id]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Friendship.objects.filter(pk=friendship.id).exists())

    def test_recipient_can_decline_request(self):
        friendship = Friendship.objects.create(
            requester=self.sender, addressee=self.recipient
        )
        self.client.force_authenticate(self.recipient)
        response = self.client.post(reverse("friend-decline", args=[friendship.id]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Friendship.objects.filter(pk=friendship.id).exists())

    def test_recipient_can_accept_request(self):
        friendship = Friendship.objects.create(
            requester=self.sender, addressee=self.recipient
        )
        self.client.force_authenticate(self.recipient)
        response = self.client.post(reverse("friend-accept", args=[friendship.id]))
        self.assertEqual(response.status_code, 200)
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, Friendship.Status.ACCEPTED)

    def test_wrong_side_cannot_cancel_or_decline(self):
        friendship = Friendship.objects.create(
            requester=self.sender, addressee=self.recipient
        )
        self.client.force_authenticate(self.recipient)
        self.assertEqual(
            self.client.post(reverse("friend-cancel", args=[friendship.id])).status_code,
            404,
        )
        self.client.force_authenticate(self.sender)
        self.assertEqual(
            self.client.post(reverse("friend-decline", args=[friendship.id])).status_code,
            404,
        )
