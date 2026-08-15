from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import UserProfile
from .ranking import league_for_points

User = get_user_model()


class LeagueRulesTests(APITestCase):
    def test_league_boundaries(self):
        self.assertEqual(league_for_points(0)["number"], 5)
        self.assertEqual(league_for_points(99)["number"], 5)
        self.assertEqual(league_for_points(100)["number"], 4)
        self.assertEqual(league_for_points(250)["number"], 3)
        self.assertEqual(league_for_points(500)["number"], 2)
        self.assertEqual(league_for_points(900)["number"], 1)


class StatisticsApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ali",
            email="ali@example.com",
            password="test-pass-123",
            first_name="Ali",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            league_points=120,
            games_played=4,
            wins=3,
            losses=1,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_statistics_returns_current_league_and_tables(self):
        response = self.client.get("/api/stats/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["me"]["league"], 4)
        self.assertEqual(response.data["me"]["league_points"], 120)
        self.assertEqual(response.data["me"]["wins"], 3)
        self.assertEqual(
            [league["number"] for league in response.data["leagues"]],
            [5, 4, 3, 2, 1],
        )

        league_four = next(
            league
            for league in response.data["leagues"]
            if league["number"] == 4
        )
        self.assertEqual(league_four["players"][0]["username"], "ali")
        self.assertEqual(league_four["players"][0]["rank"], 1)
