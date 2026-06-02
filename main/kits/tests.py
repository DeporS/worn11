from decimal import Decimal
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import Kit, Team, UserKit, UserKitImage, KitComment, KitReport, Conversation, Message, AUTOMATED_VALUATION_UNAVAILABLE_MESSAGE


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
        self.assertEqual(response.data["parent_id"], parent.id)
        self.assertEqual(response.data["reply_to_id"], parent.id)
        self.assertEqual(response.data["reply_to_username"], self.other_user.username)
        self.assertEqual(response.data["reply_count"], 0)
        self.assertEqual(parent.replies.count(), 1)

    def test_authenticated_user_can_reply_to_reply(self):
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
            reply_to=parent,
        )
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            reverse("comment-reply", args=[reply.id]),
            {"body": "Nested reply"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["parent_id"], parent.id)
        self.assertEqual(response.data["reply_to_id"], reply.id)
        self.assertEqual(response.data["reply_to_username"], self.user.username)
        created_reply = KitComment.objects.get(pk=response.data["id"])
        self.assertEqual(created_reply.parent_id, parent.id)
        self.assertEqual(created_reply.reply_to_id, reply.id)

    def test_reply_to_reply_is_grouped_under_original_top_level_comment(self):
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
            reply_to=parent,
        )
        self.client.force_authenticate(user=self.other_user)
        self.client.post(
            reverse("comment-reply", args=[reply.id]),
            {"body": "Nested reply"},
            format="json",
        )

        response = self.client.get(reverse("kit-comments", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], parent.id)
        self.assertEqual(len(response.data[0]["replies"]), 2)
        nested_reply_payload = response.data[0]["replies"][1]
        self.assertEqual(nested_reply_payload["parent_id"], parent.id)
        self.assertEqual(nested_reply_payload["reply_to_id"], reply.id)
        self.assertEqual(nested_reply_payload["reply_to_username"], self.user.username)
        self.assertEqual(nested_reply_payload["replies"], [])

    def test_comments_list_falls_back_to_parent_username_for_legacy_reply(self):
        parent = KitComment.objects.create(
            kit=self.user_kit,
            user=self.other_user,
            body="Top level",
        )
        KitComment.objects.create(
            kit=self.user_kit,
            user=self.user,
            body="Legacy reply",
            parent=parent,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("kit-comments", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["replies"][0]["reply_to_username"], self.other_user.username)

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

    def test_reply_target_must_belong_to_same_kit(self):
        parent = KitComment.objects.create(
            kit=self.user_kit,
            user=self.other_user,
            body="Top level",
        )
        foreign_reply_target = KitComment.objects.create(
            kit=self.other_user_kit,
            user=self.other_user,
            body="Other kit reply target",
        )

        with self.assertRaisesMessage(ValidationError, "Reply target must belong to the same kit."):
            KitComment.objects.create(
                kit=self.user_kit,
                user=self.user,
                body="Invalid reply target",
                parent=parent,
                reply_to=foreign_reply_target,
            )


class KitReportAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="reporter", password="password123")
        self.other_user = User.objects.create_user(username="another", password="password123")
        self.team = Team.objects.create(name="Report FC", is_verified=True)
        self.kit = Kit.objects.create(
            team=self.team,
            season="2024/2025",
            kit_type="Home",
            estimated_price=Decimal("55.00"),
        )
        self.user_kit = UserKit.objects.create(
            user=self.other_user,
            kit=self.kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )

    def test_authenticated_user_can_report_kit(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("kit-report", args=[self.user_kit.id]),
            {
                "reason": "wrong_season",
                "description": "Listed as 2008/2009 but looks like 2010/2011.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Report submitted successfully.")
        self.assertTrue(
            KitReport.objects.filter(kit=self.user_kit, reporter=self.user, reason="wrong_season").exists()
        )

    def test_unauthenticated_user_cannot_report(self):
        response = self.client.post(
            reverse("kit-report", args=[self.user_kit.id]),
            {"reason": "spam"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_duplicate_report_from_same_user_is_blocked(self):
        KitReport.objects.create(
            kit=self.user_kit,
            reporter=self.user,
            reason="wrong_team",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("kit-report", args=[self.user_kit.id]),
            {"reason": "wrong_season"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "You have already reported this kit.")

    def test_different_users_can_report_same_kit(self):
        KitReport.objects.create(
            kit=self.user_kit,
            reporter=self.user,
            reason="wrong_team",
        )
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            reverse("kit-report", args=[self.user_kit.id]),
            {"reason": "spam"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(KitReport.objects.filter(kit=self.user_kit).count(), 2)

    def test_reason_is_required(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("kit-report", args=[self.user_kit.id]),
            {"description": "Missing reason"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("reason", response.data)

    def test_invalid_reason_is_rejected(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("kit-report", args=[self.user_kit.id]),
            {"reason": "not_a_real_reason"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("reason", response.data)

    def test_other_reason_requires_description(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("kit-report", args=[self.user_kit.id]),
            {"reason": "other", "description": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("description", response.data)

    def test_other_reason_with_whitespace_only_description_is_rejected(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("kit-report", args=[self.user_kit.id]),
            {"reason": "other", "description": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("description", response.data)

    def test_valid_other_reason_with_description_succeeds(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("kit-report", args=[self.user_kit.id]),
            {"reason": "other", "description": "  Something else is wrong here.  "},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        report = KitReport.objects.get(kit=self.user_kit, reporter=self.user)
        self.assertEqual(report.description, "Something else is wrong here.")


class PublicUserKitDetailAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="detail-owner", password="password123")
        self.liker = User.objects.create_user(username="detail-liker", password="password123")
        self.team = Team.objects.create(name="Detail FC", is_verified=True)
        self.kit = Kit.objects.create(
            team=self.team,
            season="2024/2025",
            kit_type="Away",
            estimated_price=Decimal("90.00"),
        )
        self.user_kit = UserKit.objects.create(
            user=self.owner,
            kit=self.kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )
        UserKitImage.objects.create(user_kit=self.user_kit, image="user_kit_images/detail-1.jpg")
        self.user_kit.likes.add(self.liker)
        KitComment.objects.create(
            kit=self.user_kit,
            user=self.liker,
            body="Great one",
        )

    def test_public_user_can_fetch_existing_kit_detail(self):
        response = self.client.get(reverse("kit-detail", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.user_kit.id)

    def test_response_includes_images(self):
        response = self.client.get(reverse("kit-detail", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["images"]), 1)

    def test_response_includes_owner_username(self):
        response = self.client.get(reverse("kit-detail", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["owner_username"], self.owner.username)

    def test_response_includes_likes_count(self):
        response = self.client.get(reverse("kit-detail", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["likes_count"], 1)

    def test_response_includes_comments_count(self):
        response = self.client.get(reverse("kit-detail", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["comments_count"], 1)

    def test_nonexistent_kit_returns_404(self):
        response = self.client.get(reverse("kit-detail", args=[999999]))

        self.assertEqual(response.status_code, 404)


class ExploreKitsAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="explore-owner", password="password123")
        self.liker_one = User.objects.create_user(username="explore-liker-1", password="password123")
        self.liker_two = User.objects.create_user(username="explore-liker-2", password="password123")
        self.team = Team.objects.create(name="Explore FC", is_verified=True)

        self.latest_kit = self.create_user_kit(
            season="2024/2025",
            kit_type="Home",
            added_at=timezone.now() - timedelta(days=1),
        )
        self.most_liked_kit = self.create_user_kit(
            season="2023/2024",
            kit_type="Away",
            added_at=timezone.now() - timedelta(days=2),
            likes=[self.liker_one, self.liker_two],
            comments=1,
        )
        self.for_sale_kit = self.create_user_kit(
            season="2022/2023",
            kit_type="Third",
            added_at=timezone.now() - timedelta(days=3),
            for_sale=True,
            likes=[self.liker_one],
        )
        self.hidden_kit = self.create_user_kit(
            season="2021/2022",
            kit_type="Fourth",
            added_at=timezone.now() - timedelta(hours=12),
            in_the_collection=False,
        )

    def create_user_kit(
        self,
        season,
        kit_type,
        added_at,
        for_sale=False,
        in_the_collection=True,
        likes=None,
        comments=0,
    ):
        kit = Kit.objects.create(
            team=self.team,
            season=season,
            kit_type=kit_type,
            estimated_price=Decimal("80.00"),
        )
        user_kit = UserKit.objects.create(
            user=self.owner,
            kit=kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
            for_sale=for_sale,
            in_the_collection=in_the_collection,
        )
        UserKit.objects.filter(id=user_kit.id).update(added_at=added_at)
        user_kit.refresh_from_db()
        UserKitImage.objects.create(
            user_kit=user_kit,
            image=f"user_kit_images/explore-{user_kit.id}.jpg",
        )

        for liker in likes or []:
            user_kit.likes.add(liker)

        for index in range(comments):
            KitComment.objects.create(
                kit=user_kit,
                user=self.liker_one,
                body=f"Comment {index + 1}",
            )

        return user_kit

    def test_explore_kits_endpoint_returns_public_list(self):
        response = self.client.get(reverse("explore-kits"))

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 3)

    def test_latest_ordering_works(self):
        response = self.client.get(reverse("explore-kits"), {"sort": "latest"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], self.latest_kit.id)

    def test_most_liked_ordering_prioritizes_likes(self):
        response = self.client.get(reverse("explore-kits"), {"sort": "most_liked"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], self.most_liked_kit.id)

    def test_for_sale_only_returns_sale_kits(self):
        response = self.client.get(reverse("explore-kits"), {"sort": "for_sale"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.for_sale_kit.id)

    def test_invalid_sort_falls_back_to_trending(self):
        response = self.client.get(reverse("explore-kits"), {"sort": "unknown"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], self.most_liked_kit.id)

    def test_limit_is_capped(self):
        for index in range(70):
            self.create_user_kit(
                season=f"201{index}/201{index + 1}",
                kit_type=f"Variant {index}",
                added_at=timezone.now() - timedelta(days=10 + index),
            )

        response = self.client.get(reverse("explore-kits"), {"limit": 200})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 60)

    def test_response_includes_required_fields(self):
        response = self.client.get(reverse("explore-kits"))

        self.assertEqual(response.status_code, 200)
        item = response.data[0]
        self.assertIn("id", item)
        self.assertIn("owner_username", item)
        self.assertIn("kit", item)
        self.assertIn("images", item)
        self.assertIn("likes_count", item)
        self.assertIn("comments_count", item)


class MessagingAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="sender", password="password123")
        self.other_user = User.objects.create_user(username="receiver", password="password123")
        self.third_user = User.objects.create_user(username="outsider", password="password123")
        self.team = Team.objects.create(name="Messaging FC", is_verified=True)
        self.kit = Kit.objects.create(
            team=self.team,
            season="2024/2025",
            kit_type="Home",
            estimated_price=Decimal("65.00"),
        )
        self.user_kit = UserKit.objects.create(
            user=self.other_user,
            kit=self.kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )

    def test_authenticated_user_can_start_conversation_with_another_user(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("conversation-start"),
            {"username": self.other_user.username},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["other_user"]["username"], self.other_user.username)
        self.assertTrue(
            Conversation.objects.filter(
                participant_one=self.user,
                participant_two=self.other_user,
            ).exists()
            or Conversation.objects.filter(
                participant_one=self.other_user,
                participant_two=self.user,
            ).exists()
        )

    def test_cannot_start_conversation_with_self(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("conversation-start"),
            {"username": self.user.username},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("non_field_errors", response.data)

    def test_starting_same_conversation_twice_returns_same_conversation(self):
        self.client.force_authenticate(user=self.user)

        first_response = self.client.post(
            reverse("conversation-start"),
            {"username": self.other_user.username},
            format="json",
        )
        second_response = self.client.post(
            reverse("conversation-start"),
            {"username": self.other_user.username},
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response.data["id"], second_response.data["id"])
        self.assertEqual(Conversation.objects.count(), 1)

    def test_starting_conversation_by_kit_id_opens_conversation_with_kit_owner(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("conversation-start"),
            {"kit_id": self.user_kit.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["other_user"]["username"], self.other_user.username)

    def test_unauthenticated_user_cannot_access_conversations(self):
        response = self.client.get(reverse("conversation-list"))

        self.assertEqual(response.status_code, 401)

    def test_user_only_sees_their_own_conversations(self):
        first_conversation = Conversation.get_or_create_between(self.user, self.other_user)
        Conversation.get_or_create_between(self.other_user, self.third_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("conversation-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], first_conversation.id)

    def test_participant_can_list_messages(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        Message.objects.create(
            conversation=conversation,
            sender=self.user,
            body="Hello there",
        )
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(reverse("conversation-messages", args=[conversation.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertFalse(response.data["has_more"])
        self.assertEqual(response.data["results"][0]["body"], "Hello there")

    def test_initial_message_request_returns_latest_limit_in_ascending_order(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        for index in range(35):
            Message.objects.create(
                conversation=conversation,
                sender=self.user if index % 2 == 0 else self.other_user,
                body=f"Message {index + 1}",
            )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("conversation-messages", args=[conversation.id]),
            {"limit": 30},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 30)
        self.assertEqual(response.data["results"][0]["body"], "Message 6")
        self.assertEqual(response.data["results"][-1]["body"], "Message 35")
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            sorted(item["id"] for item in response.data["results"]),
        )
        self.assertTrue(response.data["has_more"])

    def test_before_message_id_returns_older_messages(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        created_messages = [
            Message.objects.create(
                conversation=conversation,
                sender=self.user if index % 2 == 0 else self.other_user,
                body=f"Message {index + 1}",
            )
            for index in range(10)
        ]
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("conversation-messages", args=[conversation.id]),
            {"limit": 3, "before": created_messages[8].id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["body"] for item in response.data["results"]],
            ["Message 6", "Message 7", "Message 8"],
        )
        self.assertTrue(response.data["has_more"])

    def test_has_more_is_false_when_older_messages_are_exhausted(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        created_messages = [
            Message.objects.create(
                conversation=conversation,
                sender=self.other_user,
                body=f"Message {index + 1}",
            )
            for index in range(3)
        ]
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("conversation-messages", args=[conversation.id]),
            {"limit": 5, "before": created_messages[2].id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["body"] for item in response.data["results"]],
            ["Message 1", "Message 2"],
        )
        self.assertFalse(response.data["has_more"])

    def test_message_limit_is_capped(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        for index in range(120):
            Message.objects.create(
                conversation=conversation,
                sender=self.user,
                body=f"Message {index + 1}",
            )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("conversation-messages", args=[conversation.id]),
            {"limit": 999},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 100)

    def test_invalid_before_message_id_returns_400(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        Message.objects.create(
            conversation=conversation,
            sender=self.user,
            body="Hello there",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("conversation-messages", args=[conversation.id]),
            {"before": "not-a-number"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("before", response.data)

    def test_before_message_id_from_another_conversation_returns_400(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        other_conversation = Conversation.get_or_create_between(self.user, self.third_user)
        foreign_message = Message.objects.create(
            conversation=other_conversation,
            sender=self.third_user,
            body="Wrong thread",
        )
        Message.objects.create(
            conversation=conversation,
            sender=self.other_user,
            body="Right thread",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("conversation-messages", args=[conversation.id]),
            {"before": foreign_message.id},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("before", response.data)

    def test_non_participant_cannot_list_messages(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        Message.objects.create(
            conversation=conversation,
            sender=self.user,
            body="Hello there",
        )
        self.client.force_authenticate(user=self.third_user)

        response = self.client.get(reverse("conversation-messages", args=[conversation.id]))

        self.assertEqual(response.status_code, 404)

    def test_participant_can_send_message(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("conversation-messages", args=[conversation.id]),
            {"body": "Hi, is this kit still available?"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["body"], "Hi, is this kit still available?")
        self.assertEqual(response.data["sender_username"], self.user.username)

    def test_non_participant_cannot_send_message(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        self.client.force_authenticate(user=self.third_user)

        response = self.client.post(
            reverse("conversation-messages", args=[conversation.id]),
            {"body": "Intruding"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_empty_message_rejected(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("conversation-messages", args=[conversation.id]),
            {"body": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("body", response.data)

    def test_message_body_is_trimmed(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("conversation-messages", args=[conversation.id]),
            {"body": "   Need more photos please   "},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["body"], "Need more photos please")

    def test_conversation_updated_at_changes_when_message_is_sent(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        old_timestamp = timezone.now() - timedelta(days=1)
        Conversation.objects.filter(pk=conversation.pk).update(updated_at=old_timestamp)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("conversation-messages", args=[conversation.id]),
            {"body": "Fresh update"},
            format="json",
        )

        conversation.refresh_from_db()

        self.assertEqual(response.status_code, 201)
        self.assertGreater(conversation.updated_at, old_timestamp)

    def test_unread_count_is_zero_when_no_messages(self):
        Conversation.get_or_create_between(self.user, self.other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("conversation-unread-count"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 0)

    def test_incoming_unread_message_increments_count_for_recipient(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        Message.objects.create(
            conversation=conversation,
            sender=self.other_user,
            body="Unread for you",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("conversation-unread-count"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 1)

    def test_own_sent_messages_do_not_count_as_unread(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        Message.objects.create(
            conversation=conversation,
            sender=self.user,
            body="My own message",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("conversation-unread-count"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 0)

    def test_fetching_messages_marks_other_users_messages_as_read(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.other_user,
            body="Please read this",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("conversation-messages", args=[conversation.id]))
        message.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(message.read_at)

    def test_unread_count_returns_to_zero_after_opening_conversation(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        Message.objects.create(
            conversation=conversation,
            sender=self.other_user,
            body="Unread before open",
        )
        self.client.force_authenticate(user=self.user)

        before_response = self.client.get(reverse("conversation-unread-count"))
        self.client.get(reverse("conversation-messages", args=[conversation.id]))
        after_response = self.client.get(reverse("conversation-unread-count"))

        self.assertEqual(before_response.data["unread_count"], 1)
        self.assertEqual(after_response.data["unread_count"], 0)

    def test_conversation_list_includes_unread_count(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        Message.objects.create(
            conversation=conversation,
            sender=self.other_user,
            body="Unread list item",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("conversation-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["unread_count"], 1)

    def test_own_messages_do_not_count_in_conversation_list_unread_count(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        Message.objects.create(
            conversation=conversation,
            sender=self.user,
            body="Own message",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("conversation-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["unread_count"], 0)

    def test_non_participant_cannot_mark_or_read_other_conversation(self):
        conversation = Conversation.get_or_create_between(self.user, self.other_user)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            body="Private thread",
        )
        self.client.force_authenticate(user=self.third_user)

        response = self.client.get(reverse("conversation-messages", args=[conversation.id]))
        message.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertIsNone(message.read_at)

    def test_unauthenticated_user_cannot_access_unread_count(self):
        response = self.client.get(reverse("conversation-unread-count"))

        self.assertEqual(response.status_code, 401)


class KitSearchSuggestionsAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("kit-search-suggestions")
        self.user = User.objects.create_user(username="variantowner", password="password123")
        self.arsenal = Team.objects.create(name="Arsenal F.C.", is_verified=True)
        self.barcelona = Team.objects.create(name="Barcelona", is_verified=True)
        self.unverified_team = Team.objects.create(name="Arsenal Legends", is_verified=False)

        self.create_kit(self.arsenal, "2018/2019", "Home")
        self.create_kit(self.arsenal, "2017/2018", "Away")
        self.create_kit(self.arsenal, "2011/2012", "Home")
        self.create_kit(self.arsenal, "2010/2011", "Away")
        self.barcelona_home = self.create_kit(self.barcelona, "2011/2012", "Home")
        self.create_kit(self.unverified_team, "2018/2019", "Home")

    def create_kit(self, team, season, kit_type):
        return Kit.objects.create(
            team=team,
            season=season,
            kit_type=kit_type,
            estimated_price=Decimal("100.00"),
        )

    def create_userkit_with_image(self, kit, image_name="preview.jpg", in_the_collection=True):
        user_kit = UserKit.objects.create(
            user=self.user,
            kit=kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
            in_the_collection=in_the_collection,
        )
        UserKitImage.objects.create(
            user_kit=user_kit,
            image=SimpleUploadedFile(image_name, b"preview-bytes", content_type="image/jpeg"),
            order=0,
        )
        return user_kit

    def test_team_name_search_returns_kit_suggestions(self):
        response = self.client.get(self.url, {"q": "Arsenal"})

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        self.assertTrue(all(item["team_name"] == "Arsenal F.C." for item in response.data))

    def test_single_digit_year_prefix_returns_recent_generated_seasons(self):
        current_year = timezone.now().year
        response = self.client.get(self.url, {"q": "Arsenal 2", "limit": "4"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                f"Arsenal F.C. {current_year}/{current_year + 1} Home",
                f"Arsenal F.C. {current_year}/{current_year + 1} Away",
                f"Arsenal F.C. {current_year}/{current_year + 1} Third",
                f"Arsenal F.C. {current_year}/{current_year + 1} Goalkeeper",
            ],
        )

    def test_two_digit_year_prefix_returns_generated_20xx_seasons(self):
        current_year = timezone.now().year
        response = self.client.get(self.url, {"q": "Arsenal 20", "limit": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["season"] for item in response.data],
            [
                f"{current_year}/{current_year + 1}",
                f"{current_year}/{current_year + 1}",
            ],
        )

    def test_two_digit_year_shorthand_returns_2021_related_seasons(self):
        response = self.client.get(self.url, {"q": "Arsenal 21", "limit": "10"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data[:10]],
            [
                "Arsenal F.C. 2021/2022 Home",
                "Arsenal F.C. 2021/2022 Away",
                "Arsenal F.C. 2021/2022 Third",
                "Arsenal F.C. 2021/2022 Goalkeeper",
                "Arsenal F.C. 2021/2022 Fourth",
                "Arsenal F.C. 2021/2022 Cup",
                "Arsenal F.C. 2021/2022 Training",
                "Arsenal F.C. 2021/2022 Special",
                "Arsenal F.C. 2020/2021 Home",
                "Arsenal F.C. 2020/2021 Away",
            ],
        )

    def test_two_digit_year_shorthand_with_home_narrows_results(self):
        response = self.client.get(self.url, {"q": "Arsenal 21 home"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2021/2022 Home",
                "Arsenal F.C. 2020/2021 Home",
            ],
        )

    def test_two_digit_year_shorthand_with_goalkeeper_alias_narrows_results(self):
        response = self.client.get(self.url, {"q": "Arsenal 21 gk"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2021/2022 Goalkeeper",
                "Arsenal F.C. 2020/2021 Goalkeeper",
            ],
        )

    def test_three_digit_year_prefix_matches_202x_seasons(self):
        response = self.client.get(self.url, {"q": "Arsenal 202", "limit": "3"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2026/2027 Home",
                "Arsenal F.C. 2026/2027 Away",
                "Arsenal F.C. 2026/2027 Third",
            ],
        )

    def test_single_year_search_returns_seasons_containing_that_year(self):
        response = self.client.get(self.url, {"q": "Arsenal 2011"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data[:8]],
            [
                "Arsenal F.C. 2011/2012 Home",
                "Arsenal F.C. 2011/2012 Away",
                "Arsenal F.C. 2011/2012 Third",
                "Arsenal F.C. 2011/2012 Goalkeeper",
                "Arsenal F.C. 2011/2012 Fourth",
                "Arsenal F.C. 2011/2012 Cup",
                "Arsenal F.C. 2011/2012 Training",
                "Arsenal F.C. 2011/2012 Special",
            ],
        )

    def test_full_year_query_returns_both_matching_seasons(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020", "limit": "16"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data[:10]],
            [
                "Arsenal F.C. 2020/2021 Home",
                "Arsenal F.C. 2020/2021 Away",
                "Arsenal F.C. 2020/2021 Third",
                "Arsenal F.C. 2020/2021 Goalkeeper",
                "Arsenal F.C. 2020/2021 Fourth",
                "Arsenal F.C. 2020/2021 Cup",
                "Arsenal F.C. 2020/2021 Training",
                "Arsenal F.C. 2020/2021 Special",
                "Arsenal F.C. 2019/2020 Home",
                "Arsenal F.C. 2019/2020 Away",
            ],
        )

    def test_historical_year_returns_1960_related_seasons(self):
        response = self.client.get(self.url, {"q": "Arsenal 1960", "limit": "10"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data[:10]],
            [
                "Arsenal F.C. 1960/1961 Home",
                "Arsenal F.C. 1960/1961 Away",
                "Arsenal F.C. 1960/1961 Third",
                "Arsenal F.C. 1960/1961 Goalkeeper",
                "Arsenal F.C. 1960/1961 Fourth",
                "Arsenal F.C. 1960/1961 Cup",
                "Arsenal F.C. 1960/1961 Training",
                "Arsenal F.C. 1960/1961 Special",
                "Arsenal F.C. 1959/1960 Home",
                "Arsenal F.C. 1959/1960 Away",
            ],
        )

    def test_historical_year_with_home_narrows_results(self):
        response = self.client.get(self.url, {"q": "Arsenal 1960 home"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 1960/1961 Home",
                "Arsenal F.C. 1959/1960 Home",
            ],
        )

    def test_minimum_supported_generated_year_is_1940(self):
        response = self.client.get(self.url, {"q": "Arsenal 1940", "limit": "10"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Arsenal F.C. 1940/1941 Home", [item["label"] for item in response.data])
        self.assertTrue(all(not item["season"].startswith("1939/") for item in response.data))

    def test_partial_slash_season_prefix_returns_only_starting_season(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020/", "limit": "8"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2020/2021 Home",
                "Arsenal F.C. 2020/2021 Away",
                "Arsenal F.C. 2020/2021 Third",
                "Arsenal F.C. 2020/2021 Goalkeeper",
                "Arsenal F.C. 2020/2021 Fourth",
                "Arsenal F.C. 2020/2021 Cup",
                "Arsenal F.C. 2020/2021 Training",
                "Arsenal F.C. 2020/2021 Special",
            ],
        )
        self.assertNotIn("Arsenal F.C. 2019/2020 Home", [item["label"] for item in response.data])

    def test_partial_slash_season_prefix_with_second_year_fragment_returns_matching_season(self):
        for query in ["Arsenal 2020/2", "Arsenal 2020/20", "Arsenal 2020/202", "Arsenal 2020/2021"]:
            with self.subTest(query=query):
                response = self.client.get(self.url, {"q": query, "limit": "2"})

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [item["label"] for item in response.data],
                    [
                        "Arsenal F.C. 2020/2021 Home",
                        "Arsenal F.C. 2020/2021 Away",
                    ],
                )

    def test_space_separated_full_season_query_returns_exact_season(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020 2021", "limit": "8"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2020/2021 Home",
                "Arsenal F.C. 2020/2021 Away",
                "Arsenal F.C. 2020/2021 Third",
                "Arsenal F.C. 2020/2021 Goalkeeper",
                "Arsenal F.C. 2020/2021 Fourth",
                "Arsenal F.C. 2020/2021 Cup",
                "Arsenal F.C. 2020/2021 Training",
                "Arsenal F.C. 2020/2021 Special",
            ],
        )

    def test_space_separated_short_season_query_normalizes_to_exact_season(self):
        response = self.client.get(self.url, {"q": "Arsenal 20 21", "limit": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2020/2021 Home",
                "Arsenal F.C. 2020/2021 Away",
            ],
        )

    def test_two_digit_space_season_pair_normalizes_to_1991_1992(self):
        response = self.client.get(self.url, {"q": "Arsenal 91 92", "limit": "8"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 1991/1992 Home",
                "Arsenal F.C. 1991/1992 Away",
                "Arsenal F.C. 1991/1992 Third",
                "Arsenal F.C. 1991/1992 Goalkeeper",
                "Arsenal F.C. 1991/1992 Fourth",
                "Arsenal F.C. 1991/1992 Cup",
                "Arsenal F.C. 1991/1992 Training",
                "Arsenal F.C. 1991/1992 Special",
            ],
        )

    def test_two_digit_slash_season_pair_normalizes_to_1991_1992(self):
        response = self.client.get(self.url, {"q": "Arsenal 91/92", "limit": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 1991/1992 Home",
                "Arsenal F.C. 1991/1992 Away",
            ],
        )

    def test_two_digit_space_season_pair_with_type_returns_only_matching_type(self):
        response = self.client.get(self.url, {"q": "Arsenal 91 92 home"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            ["Arsenal F.C. 1991/1992 Home"],
        )

    def test_minimum_two_digit_slash_season_pair_normalizes_to_1940_1941(self):
        response = self.client.get(self.url, {"q": "Arsenal 40/41", "limit": "8"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 1940/1941 Home",
                "Arsenal F.C. 1940/1941 Away",
                "Arsenal F.C. 1940/1941 Third",
                "Arsenal F.C. 1940/1941 Goalkeeper",
                "Arsenal F.C. 1940/1941 Fourth",
                "Arsenal F.C. 1940/1941 Cup",
                "Arsenal F.C. 1940/1941 Training",
                "Arsenal F.C. 1940/1941 Special",
            ],
        )

    def test_minimum_two_digit_space_season_pair_normalizes_to_1940_1941(self):
        response = self.client.get(self.url, {"q": "Arsenal 40 41", "limit": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 1940/1941 Home",
                "Arsenal F.C. 1940/1941 Away",
            ],
        )

    def test_minimum_two_digit_slash_season_pair_with_type_returns_only_matching_type(self):
        response = self.client.get(self.url, {"q": "Arsenal 40/41 away"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            ["Arsenal F.C. 1940/1941 Away"],
        )

    def test_full_year_with_partial_second_year_space_prefix_returns_1940_1941(self):
        for query in ["Arsenal 1940 1", "Arsenal 1940 19", "Arsenal 1940 194", "Arsenal 1940 1941"]:
            with self.subTest(query=query):
                response = self.client.get(self.url, {"q": query, "limit": "2"})

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [item["label"] for item in response.data],
                    [
                        "Arsenal F.C. 1940/1941 Home",
                        "Arsenal F.C. 1940/1941 Away",
                    ],
                )

    def test_full_year_with_partial_second_year_space_prefix_and_type_returns_only_matching_type(self):
        response = self.client.get(self.url, {"q": "Arsenal 1940 1 gk"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            ["Arsenal F.C. 1940/1941 Goalkeeper"],
        )

    def test_single_year_and_type_query_narrows_to_home(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020 home"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2020/2021 Home",
                "Arsenal F.C. 2019/2020 Home",
            ],
        )

    def test_space_separated_exact_season_and_type_query_returns_only_that_type(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020 2021 home"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            ["Arsenal F.C. 2020/2021 Home"],
        )

    def test_space_separated_short_exact_season_and_type_query_returns_only_that_type(self):
        response = self.client.get(self.url, {"q": "Arsenal 20 21 away"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            ["Arsenal F.C. 2020/2021 Away"],
        )

    def test_single_year_and_goalkeeper_query_uses_full_label(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020 goalkeeper"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2020/2021 Goalkeeper",
                "Arsenal F.C. 2019/2020 Goalkeeper",
            ],
        )

    def test_single_year_and_gk_query_uses_goalkeeper_alias(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020 gk"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["kit_type"] for item in response.data],
            ["Goalkeeper", "Goalkeeper"],
        )

    def test_partial_home_prefix_narrows_immediately(self):
        for query in ["Arsenal 2020 h", "Arsenal 2020 ho", "Arsenal 2020 hom", "Arsenal 2020 home"]:
            with self.subTest(query=query):
                response = self.client.get(self.url, {"q": query})

                self.assertEqual(response.status_code, 200)
                self.assertTrue(all(item["kit_type"] == "Home" for item in response.data))

    def test_partial_away_prefix_narrows_immediately(self):
        for query in ["Arsenal 2020 a", "Arsenal 2020 aw"]:
            with self.subTest(query=query):
                response = self.client.get(self.url, {"q": query})

                self.assertEqual(response.status_code, 200)
                self.assertTrue(all(item["kit_type"] == "Away" for item in response.data))

    def test_partial_goalkeeper_prefix_narrows_immediately(self):
        for query in ["Arsenal 2020 g", "Arsenal 2020 gk", "Arsenal 2020 goal", "Arsenal 2020 goalkeeper"]:
            with self.subTest(query=query):
                response = self.client.get(self.url, {"q": query})

                self.assertEqual(response.status_code, 200)
                self.assertTrue(all(item["kit_type"] == "Goalkeeper" for item in response.data))

    def test_ambiguous_t_prefix_returns_third_then_training(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020 t", "limit": "4"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2020/2021 Third",
                "Arsenal F.C. 2020/2021 Training",
                "Arsenal F.C. 2019/2020 Third",
                "Arsenal F.C. 2019/2020 Training",
            ],
        )

    def test_training_prefix_narrows_to_training(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020 tr"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(item["kit_type"] == "Training" for item in response.data))

    def test_single_year_and_type_query_matches_both_sides_of_the_season(self):
        response = self.client.get(self.url, {"q": "Arsenal 2011 home"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2011/2012 Home",
                "Arsenal F.C. 2010/2011 Home",
            ],
        )

    def test_query_without_type_returns_all_supported_types(self):
        response = self.client.get(self.url, {"q": "Arsenal 2018", "limit": "8"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["kit_type"] for item in response.data],
            [
                "Home",
                "Away",
                "Third",
                "Goalkeeper",
                "Fourth",
                "Cup",
                "Training",
                "Special",
            ],
        )

    def test_suggestions_are_generated_even_without_matching_catalog_row(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020 training"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["label"] for item in response.data],
            [
                "Arsenal F.C. 2020/2021 Training",
                "Arsenal F.C. 2019/2020 Training",
            ],
        )

    def test_away_suggestion_includes_preview_image_when_matching_upload_exists(self):
        away_kit = self.create_kit(self.arsenal, "2018/2019", "Away")
        self.create_userkit_with_image(away_kit)

        response = self.client.get(self.url, {"q": "Arsenal 2018 away"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["kit_type"], "Away")
        self.assertTrue(response.data[0]["has_uploads"])
        self.assertIsNotNone(response.data[0]["preview_image"])
        self.assertIn("/media/user_kits/", response.data[0]["preview_image"])

    def test_home_suggestion_includes_preview_image_when_matching_upload_exists(self):
        home_kit = self.create_kit(self.arsenal, "2018/2019", "Home")
        self.create_userkit_with_image(home_kit, image_name="home.jpg")

        response = self.client.get(self.url, {"q": "Arsenal 2018 home"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["kit_type"], "Home")
        self.assertTrue(response.data[0]["has_uploads"])
        self.assertIn("home", response.data[0]["preview_image"])

    def test_suggestion_has_null_preview_when_no_matching_upload_exists(self):
        response = self.client.get(self.url, {"q": "Arsenal 2025 cup"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data[0]["has_uploads"])
        self.assertIsNone(response.data[0]["preview_image"])

    def test_generated_suggestion_still_appears_without_upload(self):
        response = self.client.get(self.url, {"q": "Arsenal 2025 cup"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["label"], "Arsenal F.C. 2025/2026 Cup")

    def test_preview_matching_respects_team_season_and_type(self):
        home_kit = self.create_kit(self.arsenal, "2018/2019", "Home")
        self.create_userkit_with_image(home_kit)

        response = self.client.get(self.url, {"q": "Arsenal 2018 away"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data[0]["has_uploads"])
        self.assertIsNone(response.data[0]["preview_image"])

    def test_goalkeeper_preview_matching_supports_gk_compatibility(self):
        goalkeeper_kit = self.create_kit(self.arsenal, "2020/2021", "GK")
        self.create_userkit_with_image(goalkeeper_kit, image_name="goalkeeper.jpg")

        response = self.client.get(self.url, {"q": "Arsenal 2020 goalkeeper"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["kit_type"], "Goalkeeper")
        self.assertTrue(response.data[0]["has_uploads"])
        self.assertIn("goalkeeper", response.data[0]["preview_image"])

    def test_preview_lookup_matches_variants_visibility_for_non_collection_uploads(self):
        away_kit = self.create_kit(self.arsenal, "2018/2019", "Away")
        self.create_userkit_with_image(
            away_kit,
            image_name="away-sold.jpg",
            in_the_collection=False,
        )

        response = self.client.get(self.url, {"q": "Arsenal 2018 away"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["kit_type"], "Away")
        self.assertTrue(response.data[0]["has_uploads"])
        self.assertIn("away-sold", response.data[0]["preview_image"])

    def test_exact_season_and_type_query_filters_correctly(self):
        response = self.client.get(self.url, {"q": "Arsenal 2018/2019 away"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {
                    "team_id": self.arsenal.id,
                    "team_name": "Arsenal F.C.",
                    "team_slug": "arsenal-fc",
                    "season": "2018/2019",
                    "kit_type": "Away",
                    "label": "Arsenal F.C. 2018/2019 Away",
                    "url": "/history/team/arsenal-fc/variants?season=2018%2F2019&type=Away",
                    "preview_image": None,
                    "has_uploads": False,
                }
            ],
        )

    def test_type_matching_is_case_insensitive(self):
        response = self.client.get(self.url, {"q": "Arsenal 2018 HOME"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(item["kit_type"] == "Home" for item in response.data))

    def test_empty_and_short_queries_return_safe_empty_response(self):
        empty_response = self.client.get(self.url, {"q": ""})
        short_response = self.client.get(self.url, {"q": "a"})

        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(short_response.status_code, 200)
        self.assertEqual(empty_response.data, [])
        self.assertEqual(short_response.data, [])

    def test_default_limit_and_max_limit_cap_work(self):
        default_response = self.client.get(self.url, {"q": "Arsenal"})
        capped_response = self.client.get(self.url, {"q": "Arsenal", "limit": "50"})

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(capped_response.status_code, 200)
        self.assertEqual(len(default_response.data), 20)
        self.assertEqual(len(capped_response.data), 50)
        self.assertLessEqual(len(capped_response.data), 50)

    def test_unknown_team_returns_empty_list(self):
        response = self.client.get(self.url, {"q": "Unknown FC 2020"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_response_url_encodes_season_and_type(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020/2021 goalkeeper"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data[0]["url"],
            f"/history/team/arsenal-fc/variants?{urlencode({'season': '2020/2021', 'type': 'Goalkeeper'})}",
        )

    def test_search_suggestion_includes_team_slug(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020/2021 home"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["team_slug"], "arsenal-fc")

    def test_team_slug_generation_uses_slugified_name(self):
        response = self.client.get(self.url, {"q": "Arsenal 2020/2021 home"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["url"], "/history/team/arsenal-fc/variants?season=2020%2F2021&type=Home")

    def test_team_resolve_accepts_slug(self):
        response = self.client.get(reverse("team-resolve", args=["arsenal-fc"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.arsenal.id)
        self.assertEqual(response.data["name"], "Arsenal F.C.")
        self.assertEqual(response.data["slug"], "arsenal-fc")

    def test_team_resolve_accepts_numeric_id(self):
        response = self.client.get(reverse("team-resolve", args=[str(self.arsenal.id)]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.arsenal.id)

    def test_kit_variants_api_accepts_team_slug(self):
        UserKit.objects.create(
            user=self.user,
            kit=self.barcelona_home,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )

        response = self.client.get(
            reverse("kit-variants", args=["barcelona"]),
            {"season": "2011/2012", "type": "Home"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["kit"]["team"]["name"], "Barcelona")

    def test_kit_variants_api_accepts_numeric_team_id(self):
        UserKit.objects.create(
            user=self.user,
            kit=self.barcelona_home,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )

        response = self.client.get(
            reverse("kit-variants", args=[str(self.barcelona.id)]),
            {"season": "2011/2012", "type": "Home"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["kit"]["team"]["name"], "Barcelona")
