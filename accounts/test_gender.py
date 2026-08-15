from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import UserProfile
from .serializers import RegisterSerializer, UserSerializer, UserUpdateSerializer


User = get_user_model()


class UserGenderTests(TestCase):
    def test_registration_requires_and_saves_gender(self):
        serializer = RegisterSerializer(
            data={
                "username": "ali_gender",
                "email": "ali-gender@example.com",
                "gender": UserProfile.Gender.MALE,
                "password": "strongpass123",
                "password_confirm": "strongpass123",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        user.refresh_from_db()
        user.profile.refresh_from_db()

        self.assertEqual(user.profile.gender, UserProfile.Gender.MALE)
        self.assertEqual(UserSerializer(user).data["gender"], "male")

    def test_profile_update_changes_gender(self):
        user = User.objects.create_user(
            username="profile_gender",
            email="profile-gender@example.com",
            password="strongpass123",
            first_name="Profile",
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.gender = UserProfile.Gender.MALE
        profile.save(update_fields=["gender", "updated_at"])

        serializer = UserUpdateSerializer(
            user,
            data={
                "username": "profile_gender",
                "email": "profile-gender@example.com",
                "first_name": "Profile",
                "gender": UserProfile.Gender.FEMALE,
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        user.profile.refresh_from_db()

        self.assertEqual(user.profile.gender, UserProfile.Gender.FEMALE)
        self.assertEqual(UserSerializer(user).data["gender"], "female")

    def test_registration_rejects_missing_gender(self):
        serializer = RegisterSerializer(
            data={
                "username": "missing_gender",
                "email": "missing-gender@example.com",
                "password": "strongpass123",
                "password_confirm": "strongpass123",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("gender", serializer.errors)
