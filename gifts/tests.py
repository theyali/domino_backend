from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from restaurants.models import Restaurant
from rooms.models import GameRoom, RoomPlayer

from .models import Gift, InventoryGift


User = get_user_model()


class GiftApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ali",
            email="ali@example.com",
            password="secret123",
        )
        self.other_user = User.objects.create_user(
            username="john",
            email="john@example.com",
            password="secret123",
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.restaurant = Restaurant.objects.create(
            name="Mangal Steak House",
            is_active=True,
        )
        self.other_restaurant = Restaurant.objects.create(
            name="Dolma Restaurant",
            is_active=True,
        )

        self.hookah = Gift.objects.create(
            restaurant=self.restaurant,
            name="Кальян",
            price="25.00",
            image="gifts/hookah.png",
        )
        self.tea = Gift.objects.create(
            restaurant=self.restaurant,
            name="Чай",
            price="8.00",
        )
        Gift.objects.create(
            restaurant=self.restaurant,
            name="Скрытый подарок",
            price="1.00",
            is_active=False,
        )
        Gift.objects.create(
            restaurant=self.other_restaurant,
            name="Dolma Gift",
            price="15.00",
        )

    def test_restaurant_gifts_require_authentication(self):
        self.client.credentials()
        response = self.client.get(
            reverse("restaurant-gifts", args=[self.restaurant.id])
        )
        self.assertEqual(response.status_code, 401)

    def test_restaurant_gifts_returns_only_active_gifts_for_that_restaurant(self):
        response = self.client.get(
            reverse("restaurant-gifts", args=[self.restaurant.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.data], ["Чай", "Кальян"])
        self.assertTrue(
            all(item["restaurant_id"] == self.restaurant.id for item in response.data)
        )

        tea_data = next(item for item in response.data if item["name"] == "Чай")
        hookah_data = next(item for item in response.data if item["name"] == "Кальян")

        self.assertIsNone(tea_data["image_url"])
        self.assertEqual(
            hookah_data["image_url"],
            "http://testserver/media/gifts/hookah.png",
        )

    def test_inventory_returns_only_current_user_items(self):
        mine = InventoryGift.objects.create(owner=self.user, gift=self.hookah)
        InventoryGift.objects.create(owner=self.other_user, gift=self.tea)

        response = self.client.get(reverse("inventory-gifts"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], mine.id)
        self.assertEqual(response.data[0]["gift"]["name"], "Кальян")
        self.assertEqual(
            response.data[0]["gift"]["image_url"],
            "http://testserver/media/gifts/hookah.png",
        )
        self.assertEqual(
            response.data[0]["qr_code"],
            f"domino-gift://redeem/{mine.qr_token}",
        )

    def test_inventory_detail_cannot_read_another_users_gift(self):
        item = InventoryGift.objects.create(owner=self.other_user, gift=self.tea)

        response = self.client.get(
            reverse("inventory-gift-detail", args=[item.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_inventory_qr_tokens_are_unique(self):
        first = InventoryGift.objects.create(owner=self.user, gift=self.hookah)
        second = InventoryGift.objects.create(owner=self.user, gift=self.hookah)

        self.assertNotEqual(first.qr_token, second.qr_token)
        self.assertNotEqual(first.qr_code, second.qr_code)


class MultiplayerGiftTests(APITestCase):
    def setUp(self):
        self.ali = User.objects.create_user(username="ali", password="secret123")
        self.john = User.objects.create_user(username="john", password="secret123")
        self.alex = User.objects.create_user(username="alex", password="secret123")
        self.annie = User.objects.create_user(username="annie", password="secret123")

        token = Token.objects.create(user=self.ali)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        self.restaurant = Restaurant.objects.create(
            name="Gift Room Restaurant",
            is_active=True,
        )
        self.room = GameRoom.objects.create(
            restaurant=self.restaurant,
            owner_name="Ali",
            max_players=4,
            status=GameRoom.Status.PLAYING,
        )
        self.ali_player = RoomPlayer.objects.create(
            room=self.room,
            user=self.ali,
            name="Ali",
            seat_index=0,
            is_owner=True,
        )
        self.john_player = RoomPlayer.objects.create(
            room=self.room,
            user=self.john,
            name="John",
            seat_index=1,
        )
        self.alex_player = RoomPlayer.objects.create(
            room=self.room,
            user=self.alex,
            name="Alex",
            seat_index=2,
        )
        self.annie_player = RoomPlayer.objects.create(
            room=self.room,
            user=self.annie,
            name="Annie",
            seat_index=3,
        )
        self.hookah = Gift.objects.create(
            restaurant=self.restaurant,
            name="Кальян",
            price="20.00",
        )
        self.beer = Gift.objects.create(
            restaurant=self.restaurant,
            name="Пиво",
            price="10.00",
        )

    def _send(self, gift, recipients):
        return self.client.post(
            reverse("send-room-gift", args=[self.room.id]),
            {
                "gift_id": gift.id,
                "recipient_player_ids": recipients,
            },
            format="json",
        )

    def test_cannot_send_gift_to_self(self):
        item = InventoryGift.objects.create(owner=self.ali, gift=self.hookah)

        response = self._send(self.hookah, [self.ali_player.id])

        self.assertEqual(response.status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.owner_id, self.ali.id)

    def test_send_same_gift_to_three_players_transfers_three_inventory_items(self):
        items = [
            InventoryGift.objects.create(owner=self.ali, gift=self.hookah)
            for _ in range(3)
        ]

        response = self._send(
            self.hookah,
            [self.john_player.id, self.alex_player.id, self.annie_player.id],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["recipient_player_ids"]), 3)

        expected_owners = {self.john.id, self.alex.id, self.annie.id}
        actual_owners = set(
            InventoryGift.objects.filter(id__in=[item.id for item in items])
            .values_list("owner_id", flat=True)
        )
        self.assertEqual(actual_owners, expected_owners)

        for player in (
            self.john_player,
            self.alex_player,
            self.annie_player,
        ):
            player.refresh_from_db()
            self.assertEqual(player.active_gift_id, self.hookah.id)

    def test_new_gift_replaces_only_avatar_active_gift(self):
        old_item = InventoryGift.objects.create(owner=self.ali, gift=self.hookah)
        new_item = InventoryGift.objects.create(owner=self.ali, gift=self.beer)

        first = self._send(self.hookah, [self.john_player.id])
        self.assertEqual(first.status_code, 200)

        second = self._send(self.beer, [self.john_player.id])
        self.assertEqual(second.status_code, 200)

        self.john_player.refresh_from_db()
        old_item.refresh_from_db()
        new_item.refresh_from_db()

        self.assertEqual(self.john_player.active_gift_id, self.beer.id)
        self.assertEqual(old_item.owner_id, self.john.id)
        self.assertEqual(new_item.owner_id, self.john.id)

    def test_not_enough_copies_rolls_back_entire_multi_send(self):
        items = [
            InventoryGift.objects.create(owner=self.ali, gift=self.hookah)
            for _ in range(2)
        ]

        response = self._send(
            self.hookah,
            [self.john_player.id, self.alex_player.id, self.annie_player.id],
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            all(
                InventoryGift.objects.get(pk=item.id).owner_id == self.ali.id
                for item in items
            )
        )
        self.john_player.refresh_from_db()
        self.alex_player.refresh_from_db()
        self.annie_player.refresh_from_db()
        self.assertIsNone(self.john_player.active_gift_id)
        self.assertIsNone(self.alex_player.active_gift_id)
        self.assertIsNone(self.annie_player.active_gift_id)
