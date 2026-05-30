from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from .models import Kit, Team, UserKit, AUTOMATED_VALUATION_UNAVAILABLE_MESSAGE


class UserKitPricingTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="collector", password="password123")
        self.client.force_authenticate(user=self.user)

        self.team_zero = Team.objects.create(name="Zero FC", is_verified=True)
        self.team_positive = Team.objects.create(name="Value FC", is_verified=True)
        self.team_update = Team.objects.create(name="Update FC", is_verified=True)

    def test_create_userkit_with_missing_estimated_price_succeeds_and_warns(self):
        response = self.client.post(
            reverse("api-my-collection"),
            {
                "team_name": self.team_zero.name,
                "season": "2024/2025",
                "kit_type": "Home",
                "size": "L",
                "condition": "VERY_GOOD",
                "shirt_technology": "REPLICA",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data["final_value"]), Decimal("0.00"))
        self.assertEqual(response.data["valuation_warning"], AUTOMATED_VALUATION_UNAVAILABLE_MESSAGE)

    def test_create_userkit_with_estimated_price_calculates_value(self):
        kit = Kit.objects.create(
            team=self.team_positive,
            season="2024/2025",
            kit_type="Away",
            estimated_price=Decimal("100.00"),
        )

        response = self.client.post(
            reverse("api-my-collection"),
            {
                "team_name": kit.team.name,
                "season": kit.season,
                "kit_type": kit.kit_type,
                "size": "M",
                "condition": "VERY_GOOD",
                "shirt_technology": "REPLICA",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data["final_value"]), Decimal("90.00"))
        self.assertIsNone(response.data["valuation_warning"])

    def test_update_userkit_with_missing_estimated_price_succeeds_and_warns(self):
        starting_kit = Kit.objects.create(
            team=self.team_positive,
            season="2023/2024",
            kit_type="Home",
            estimated_price=Decimal("120.00"),
        )
        user_kit = UserKit.objects.create(
            user=self.user,
            kit=starting_kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )

        response = self.client.patch(
            reverse("api-my-collection-detail", args=[user_kit.id]),
            {
                "team_name": self.team_update.name,
                "season": "2025/2026",
                "kit_type": "Third",
                "size": "L",
                "condition": "VERY_GOOD",
                "shirt_technology": "REPLICA",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data["final_value"]), Decimal("0.00"))
        self.assertEqual(response.data["valuation_warning"], AUTOMATED_VALUATION_UNAVAILABLE_MESSAGE)

    def test_userkit_save_handles_none_estimated_price_in_memory(self):
        kit = Kit.objects.create(
            team=self.team_zero,
            season="2025/2026",
            kit_type="Fourth",
            estimated_price=Decimal("0.00"),
        )
        kit.estimated_price = None

        user_kit = UserKit.objects.create(
            user=self.user,
            kit=kit,
            shirt_technology="PLAYER_ISSUE",
            condition="GOOD",
            size="S",
        )

        self.assertEqual(user_kit.final_value, Decimal("0.00"))
        self.assertEqual(user_kit.get_valuation_warning(), AUTOMATED_VALUATION_UNAVAILABLE_MESSAGE)
