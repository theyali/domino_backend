from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from restaurants.models import Restaurant

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
            icon_url="https://example.com/hookah.png",
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
        self.assertTrue(all(item["restaurant_id"] == self.restaurant.id for item in response.data))

    def test_inventory_returns_only_current_user_items(self):
        mine = InventoryGift.objects.create(owner=self.user, gift=self.hookah)
        InventoryGift.objects.create(owner=self.other_user, gift=self.tea)

        response = self.client.get(reverse("inventory-gifts"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], mine.id)
        self.assertEqual(response.data[0]["gift"]["name"], "Кальян")
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
