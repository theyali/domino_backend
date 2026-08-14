from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AccountsApiTests(APITestCase):
    def test_register_returns_token_and_user(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "ali",
                "email": "ali@example.com",
                "password": "password123",
                "password_confirm": "password123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["token"])
        self.assertEqual(response.data["user"]["username"], "ali")
        self.assertIsNone(response.data["user"]["avatar_url"])
        self.assertEqual(User.objects.count(), 1)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(
            username="first",
            email="same@example.com",
            password="password123",
        )

        response = self.client.post(
            reverse("auth-register"),
            {
                "username": "second",
                "email": "same@example.com",
                "password": "password123",
                "password_confirm": "password123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_and_me(self):
        User.objects.create_user(
            username="john",
            email="john@example.com",
            password="password123",
        )

        login = self.client.post(
            reverse("auth-login"),
            {"username": "john", "password": "password123"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

        token = login.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        me = self.client.get(reverse("auth-me"))

        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["username"], "john")

    def test_me_patch_updates_profile_and_avatar(self):
        User.objects.create_user(
            username="ali",
            email="old@example.com",
            password="password123",
            first_name="Ali",
        )
        login = self.client.post(
            reverse("auth-login"),
            {"username": "ali", "password": "password123"},
            format="json",
        )
        token = login.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

        image_buffer = BytesIO()
        Image.new("RGB", (4, 4), "white").save(image_buffer, format="PNG")
        avatar = SimpleUploadedFile(
            "avatar.png",
            image_buffer.getvalue(),
            content_type="image/png",
        )

        response = self.client.patch(
            reverse("auth-me"),
            {
                "username": "ali_new",
                "email": "new@example.com",
                "first_name": "Ali Updated",
                "avatar": avatar,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "ali_new")
        self.assertEqual(response.data["email"], "new@example.com")
        self.assertEqual(response.data["first_name"], "Ali Updated")
        self.assertTrue(response.data["avatar_url"].startswith("/media/avatars/"))

    def test_logout_invalidates_token(self):
        user = User.objects.create_user(
            username="annie",
            email="annie@example.com",
            password="password123",
        )
        login = self.client.post(
            reverse("auth-login"),
            {"username": "annie", "password": "password123"},
            format="json",
        )
        token = login.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

        logout = self.client.post(reverse("auth-logout"))
        self.assertEqual(logout.status_code, status.HTTP_204_NO_CONTENT)

        me = self.client.get(reverse("auth-me"))
        self.assertEqual(me.status_code, status.HTTP_401_UNAUTHORIZED)
