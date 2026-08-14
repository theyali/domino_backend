from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Restaurant


class RestaurantApiTests(APITestCase):
    def test_list_restaurants_uses_flutter_compatible_fields(self):
        Restaurant.objects.create(name="Mangal Steak House", is_active=True)

        response = self.client.get(reverse("restaurant-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["name"], "Mangal Steak House")
        self.assertEqual(response.data[0]["players"], 0)
        self.assertTrue(response.data[0]["active"])
