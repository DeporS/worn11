from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from .models import Kit, Team, UserKit, KitComment, AUTOMATED_VALUATION_UNAVAILABLE_MESSAGE


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


class UserKitCollectionFlagTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="collector2", password="password123")
        self.client.force_authenticate(user=self.user)
        self.team = Team.objects.create(name="Flag FC", is_verified=True)
        self.kit = Kit.objects.create(
            team=self.team,
            season="2024/2025",
            kit_type="Home",
            estimated_price=Decimal("50.00"),
        )

    def test_create_defaults_in_the_collection_to_true(self):
        response = self.client.post(
            reverse("api-my-collection"),
            {
                "team_name": self.team.name,
                "season": self.kit.season,
                "kit_type": self.kit.kit_type,
                "size": "L",
                "condition": "VERY_GOOD",
                "shirt_technology": "REPLICA",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["in_the_collection"])

    def test_update_can_set_in_the_collection_false(self):
        user_kit = UserKit.objects.create(
            user=self.user,
            kit=self.kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )

        response = self.client.patch(
            reverse("api-my-collection-detail", args=[user_kit.id]),
            {
                "in_the_collection": False,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["in_the_collection"])

    def test_update_other_fields_preserves_in_the_collection(self):
        user_kit = UserKit.objects.create(
            user=self.user,
            kit=self.kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
            in_the_collection=False,
        )

        response = self.client.patch(
            reverse("api-my-collection-detail", args=[user_kit.id]),
            {
                "size": "M",
                "condition": "GOOD",
                "shirt_technology": "PLAYER_ISSUE",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["in_the_collection"])


class KitCommentAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="commenter", password="password123")
        self.other_user = User.objects.create_user(username="other", password="password123")
        self.moderator = User.objects.create_user(username="mod", password="password123")
        self.moderator.profile.is_moderator = True
        self.moderator.profile.save()

        self.team = Team.objects.create(name="Comment FC", is_verified=True)
        self.kit = Kit.objects.create(
            team=self.team,
            season="2024/2025",
            kit_type="Home",
            estimated_price=Decimal("75.00"),
        )
        self.other_kit = Kit.objects.create(
            team=self.team,
            season="2025/2026",
            kit_type="Away",
            estimated_price=Decimal("80.00"),
        )
        self.user_kit = UserKit.objects.create(
            user=self.user,
            kit=self.kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )
        self.other_user_kit = UserKit.objects.create(
            user=self.other_user,
            kit=self.other_kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )

    def test_authenticated_user_can_create_top_level_comment(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("kit-comments", args=[self.user_kit.id]),
            {"body": "  Great shirt  "},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["body"], "Great shirt")
        self.assertEqual(response.data["user"]["username"], self.user.username)
        self.assertEqual(response.data["likes_count"], 0)
        self.assertEqual(response.data["reply_count"], 0)

    def test_unauthenticated_user_cannot_create_comment(self):
        response = self.client.post(
            reverse("kit-comments", args=[self.user_kit.id]),
            {"body": "Not allowed"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_authenticated_user_can_reply_to_top_level_comment(self):
        parent = KitComment.objects.create(
            kit=self.user_kit,
            user=self.other_user,
            body="Top level",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("comment-reply", args=[parent.id]),
            {"body": "Reply text"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["body"], "Reply text")
        self.assertEqual(response.data["reply_count"], 0)
        self.assertEqual(parent.replies.count(), 1)

    def test_replying_to_a_reply_is_blocked(self):
        parent = KitComment.objects.create(
            kit=self.user_kit,
            user=self.other_user,
            body="Top level",
        )
        reply = KitComment.objects.create(
            kit=self.user_kit,
            user=self.user,
            body="Reply",
            parent=parent,
        )
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            reverse("comment-reply", args=[reply.id]),
            {"body": "Nested reply"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("parent", response.data)

    def test_user_can_like_and_unlike_comment(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.other_user,
            body="Like me",
        )
        self.client.force_authenticate(user=self.user)

        like_response = self.client.post(reverse("comment-like", args=[comment.id]))
        unlike_response = self.client.post(reverse("comment-like", args=[comment.id]))

        self.assertEqual(like_response.status_code, 200)
        self.assertTrue(like_response.data["liked"])
        self.assertEqual(like_response.data["likes_count"], 1)
        self.assertEqual(unlike_response.status_code, 200)
        self.assertFalse(unlike_response.data["liked"])
        self.assertEqual(unlike_response.data["likes_count"], 0)

    def test_likes_count_updates_in_comments_list(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.other_user,
            body="Popular",
        )
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse("comment-like", args=[comment.id]))

        response = self.client.get(reverse("kit-comments", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["likes_count"], 1)
        self.assertTrue(response.data[0]["is_liked_by_me"])

    def test_user_can_delete_own_comment(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.user,
            body="Mine",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(reverse("comment-delete", args=[comment.id]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(KitComment.objects.filter(id=comment.id).exists())

    def test_user_cannot_delete_another_users_comment(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.other_user,
            body="Not yours",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(reverse("comment-delete", args=[comment.id]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(KitComment.objects.filter(id=comment.id).exists())

    def test_moderator_can_delete_any_comment(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.other_user,
            body="Moderator target",
        )
        self.client.force_authenticate(user=self.moderator)

        response = self.client.delete(reverse("comment-delete", args=[comment.id]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(KitComment.objects.filter(id=comment.id).exists())

    def test_parent_reply_must_belong_to_same_kit(self):
        foreign_parent = KitComment.objects.create(
            kit=self.other_user_kit,
            user=self.other_user,
            body="Other kit comment",
        )

        with self.assertRaisesMessage(ValidationError, "Reply must belong to the same kit."):
            KitComment.objects.create(
                kit=self.user_kit,
                user=self.user,
                body="Invalid reply",
                parent=foreign_parent,
            )
