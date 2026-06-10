from decimal import Decimal
from datetime import timedelta
from importlib import import_module
from urllib.parse import urlencode
from unittest.mock import patch

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import Country, League, Kit, KitType, KitTypeAlias, TeamSeasonKitType, KitTypeModerationAction, TeamModerationAction, ShirtVersion, Team, UserKit, UserKitImage, WishlistItem, KitComment, KitCommentLike, KitReport, Conversation, Message, Follow, Notification, CollectionValueSnapshot, AUTOMATED_VALUATION_UNAVAILABLE_MESSAGE, TECHNOLOGIE_MULTIPLIERS, calculate_collection_total_value
from .serializers import KitSerializer, TeamSerializer, UserKitSerializer, WishlistItemSerializer


class CatalogFoundationTests(APITestCase):
    @staticmethod
    def run_catalog_backfill():
        migration = import_module(
            'kits.migrations.0029_shirtversion_kittype_kit_kit_type_ref_and_more'
        )
        migration.seed_and_backfill_catalogs(django_apps, None)

    def setUp(self):
        self.user = User.objects.create_user(username='catalog_collector', password='password123')
        self.team = Team.objects.create(name='Catalog FC', is_verified=True)

    def test_seeded_kit_types_exist_with_expected_metadata(self):
        expected = {
            'HOME': ('Home', 'outfield', 'primary', 10),
            'GOALKEEPER': ('Goalkeeper', 'goalkeeper', 'primary', 70),
            'SECOND_GOALKEEPER': ('Second Goalkeeper', 'goalkeeper', 'expanded', 80),
            'ANNIVERSARY': ('Anniversary', 'special', 'none', 110),
            'RETRO_REISSUE': ('Retro/Reissue', 'special', 'none', 180),
        }

        for code, values in expected.items():
            kit_type = KitType.objects.get(canonical_code=code)
            self.assertEqual(
                (kit_type.name, kit_type.category, kit_type.default_visibility, kit_type.sort_order),
                values,
            )
            self.assertEqual(kit_type.status, 'approved')

        self.assertEqual(KitType.objects.filter(status='approved').count(), 18)

    def test_seeded_aliases_cover_legacy_and_collector_names(self):
        expected = {
            'gk': 'GOALKEEPER',
            'goalkeeper': 'GOALKEEPER',
            'special edition': 'SPECIAL',
            'special': 'SPECIAL',
            '2nd gk': 'SECOND_GOALKEEPER',
            'champions league': 'EUROPEAN',
        }

        for alias, code in expected.items():
            self.assertEqual(
                KitTypeAlias.objects.get(alias_normalized=alias).kit_type.canonical_code,
                code,
            )

    def test_duplicate_normalized_alias_is_rejected(self):
        goalkeeper = KitType.objects.get(canonical_code='GOALKEEPER')

        with self.assertRaises(IntegrityError), transaction.atomic():
            KitTypeAlias.objects.create(alias_normalized='gk', kit_type=goalkeeper)

    def test_seeded_shirt_versions_preserve_legacy_multipliers(self):
        expected = {
            'REPLICA': Decimal('1.000'),
            'PLAYER_ISSUE': Decimal('1.500'),
            'MATCH_WORN': Decimal('5.000'),
        }

        for code, multiplier in expected.items():
            version = ShirtVersion.objects.get(code=code)
            self.assertEqual(version.valuation_multiplier, multiplier)
            self.assertEqual(version.valuation_multiplier, TECHNOLOGIE_MULTIPLIERS[code])

    def test_supporter_code_is_displayed_as_stadium(self):
        stadium = ShirtVersion.objects.get(code='SUPPORTER')

        self.assertEqual(stadium.name, 'Stadium')
        self.assertEqual(stadium.valuation_multiplier, Decimal('1.000'))

    def test_uncertain_versions_use_conservative_valuation(self):
        conservative_codes = [
            'TEAM_ISSUED',
            'MATCH_ISSUE',
            'MATCH_PREPARED',
            'TRAINING_ISSUE',
            'SAMPLE',
            'PROTOTYPE',
        ]

        for version in ShirtVersion.objects.filter(code__in=conservative_codes):
            self.assertEqual(version.valuation_multiplier, Decimal('1.000'))
            self.assertTrue(version.manual_value_recommended)

        self.assertEqual(
            ShirtVersion.objects.filter(code__in=conservative_codes).count(),
            len(conservative_codes),
        )

    def test_product_technologies_are_not_shirt_versions(self):
        prohibited_terms = [
            'adizero',
            'climacool',
            'aeroready',
            'heat.rdy',
            'dri-fit',
            'vaporknit',
            'drycell',
        ]
        catalog_text = ' '.join(
            f'{version.code} {version.name}'.lower()
            for version in ShirtVersion.objects.all()
        )

        for term in prohibited_terms:
            self.assertNotIn(term, catalog_text)

    def test_backfill_maps_kit_and_wishlist_types_without_changing_legacy_text(self):
        kits = [
            Kit.objects.create(team=self.team, season='2020/2021', kit_type='Home'),
            Kit.objects.create(team=self.team, season='2021/2022', kit_type='GK'),
            Kit.objects.create(team=self.team, season='2022/2023', kit_type='Goalkeeper'),
            Kit.objects.create(team=self.team, season='2023/2024', kit_type='Special Edition'),
            Kit.objects.create(team=self.team, season='2024/2025', kit_type='Special'),
        ]
        wishlist_item = WishlistItem.objects.create(
            user=self.user,
            team=self.team,
            season='2021/2022',
            kit_type='Goalkeeper',
        )

        self.run_catalog_backfill()

        expected_codes = ['HOME', 'GOALKEEPER', 'GOALKEEPER', 'SPECIAL', 'SPECIAL']
        for kit, expected_code in zip(kits, expected_codes):
            kit.refresh_from_db()
            self.assertEqual(kit.kit_type_ref.canonical_code, expected_code)

        self.assertEqual(kits[1].kit_type, 'GK')
        self.assertEqual(kits[3].kit_type, 'Special Edition')
        wishlist_item.refresh_from_db()
        self.assertEqual(wishlist_item.kit_type_ref.canonical_code, 'GOALKEEPER')
        self.assertEqual(wishlist_item.kit_type, 'Goalkeeper')

    def test_unknown_legacy_type_creates_pending_catalog_entry(self):
        kit = Kit.objects.create(
            team=self.team,
            season='2004/2005',
            kit_type='One-off Celebration',
        )

        self.run_catalog_backfill()

        kit.refresh_from_db()
        self.assertEqual(kit.kit_type, 'One-off Celebration')
        self.assertEqual(kit.kit_type_ref.name, 'One-off Celebration')
        self.assertEqual(kit.kit_type_ref.status, 'pending')
        self.assertEqual(kit.kit_type_ref.category, 'other')
        self.assertEqual(kit.kit_type_ref.default_visibility, 'none')

    def test_backfill_preserves_values_totals_and_snapshots(self):
        base_price = Decimal('100.00')
        expected_values = {
            'REPLICA': Decimal('100.00'),
            'PLAYER_ISSUE': Decimal('150.00'),
            'MATCH_WORN': Decimal('500.00'),
        }
        user_kits = []

        for index, (technology, expected_value) in enumerate(expected_values.items()):
            kit = Kit.objects.create(
                team=self.team,
                season=f'20{index:02d}/20{index + 1:02d}',
                kit_type='Away',
                estimated_price=base_price,
            )
            user_kit = UserKit.objects.create(
                user=self.user,
                kit=kit,
                shirt_technology=technology,
                condition='VERY_GOOD',
                size='L',
            )
            self.assertEqual(user_kit.final_value, expected_value)
            user_kits.append(user_kit)

        total_before = calculate_collection_total_value(self.user)
        snapshots_before = CollectionValueSnapshot.objects.count()
        stored_values_before = {
            user_kit.pk: user_kit.final_value for user_kit in user_kits
        }

        self.run_catalog_backfill()

        expected_version_codes = ['REPLICA', 'PLAYER_ISSUE', 'MATCH_WORN']
        for user_kit, expected_code in zip(user_kits, expected_version_codes):
            user_kit.refresh_from_db()
            self.assertEqual(user_kit.shirt_version.code, expected_code)
            self.assertEqual(user_kit.final_value, stored_values_before[user_kit.pk])

        self.assertEqual(calculate_collection_total_value(self.user), total_before)
        self.assertEqual(CollectionValueSnapshot.objects.count(), snapshots_before)

    def test_manual_value_still_overrides_automatic_valuation(self):
        kit = Kit.objects.create(
            team=self.team,
            season='2025/2026',
            kit_type='Third',
            estimated_price=Decimal('100.00'),
        )
        user_kit = UserKit.objects.create(
            user=self.user,
            kit=kit,
            shirt_technology='MATCH_WORN',
            condition='VERY_GOOD',
            size='L',
            manual_value=Decimal('123.45'),
        )

        self.assertEqual(user_kit.final_value, Decimal('123.45'))

        self.run_catalog_backfill()
        user_kit.refresh_from_db()
        self.assertEqual(user_kit.final_value, Decimal('123.45'))


class CatalogCompatibilityAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='compatibility_owner', password='password123')
        self.team = Team.objects.create(name='Compatibility FC', is_verified=True)
        self.home_type = KitType.objects.get(canonical_code='HOME')
        self.replica_version = ShirtVersion.objects.get(code='REPLICA')

    def create_user_kit(self, *, with_catalog_refs=True, technology='REPLICA'):
        kit = Kit.objects.create(
            team=self.team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type if with_catalog_refs else None,
            estimated_price=Decimal('100.00'),
        )
        return UserKit.objects.create(
            user=self.user,
            kit=kit,
            shirt_technology=technology,
            shirt_version=(
                ShirtVersion.objects.get(code=technology)
                if with_catalog_refs
                else None
            ),
            condition='VERY_GOOD',
            size='L',
        )

    def test_kit_serializer_keeps_legacy_type_and_adds_catalog_fields(self):
        user_kit = self.create_user_kit()

        data = KitSerializer(user_kit.kit).data

        self.assertEqual(data['kit_type'], 'Home')
        self.assertEqual(data['kit_type_id'], self.home_type.id)
        self.assertEqual(data['kit_type_slug'], 'home')
        self.assertEqual(data['kit_type_display'], 'Home')
        self.assertEqual(data['kit_type_canonical_code'], 'HOME')

    def test_kit_serializer_falls_back_when_catalog_reference_is_null(self):
        kit = Kit.objects.create(
            team=self.team,
            season='2023/2024',
            kit_type='Legacy Celebration',
        )

        data = KitSerializer(kit).data

        self.assertEqual(data['kit_type'], 'Legacy Celebration')
        self.assertIsNone(data['kit_type_id'])
        self.assertIsNone(data['kit_type_slug'])
        self.assertEqual(data['kit_type_display'], 'Legacy Celebration')
        self.assertIsNone(data['kit_type_canonical_code'])

    def test_userkit_serializer_keeps_legacy_version_fields_and_adds_catalog_fields(self):
        self.replica_version.valuation_note = 'Use automatic valuation for standard retail shirts.'
        self.replica_version.save(update_fields=['valuation_note'])
        user_kit = self.create_user_kit()

        data = UserKitSerializer(user_kit).data

        self.assertEqual(data['shirt_technology'], 'REPLICA')
        self.assertEqual(data['technology_display'], 'Replica')
        self.assertEqual(data['shirt_version_id'], self.replica_version.id)
        self.assertEqual(data['shirt_version_code'], 'REPLICA')
        self.assertEqual(data['shirt_version_display'], 'Replica')
        self.assertFalse(data['shirt_version_manual_value_recommended'])
        self.assertEqual(
            data['shirt_version_valuation_note'],
            'Use automatic valuation for standard retail shirts.',
        )

    def test_userkit_serializer_falls_back_to_legacy_technology(self):
        user_kit = self.create_user_kit(with_catalog_refs=False, technology='PLAYER_ISSUE')

        data = UserKitSerializer(user_kit).data

        self.assertEqual(data['shirt_technology'], 'PLAYER_ISSUE')
        self.assertEqual(data['technology_display'], 'Player Issue')
        self.assertIsNone(data['shirt_version_id'])
        self.assertEqual(data['shirt_version_code'], 'PLAYER_ISSUE')
        self.assertEqual(data['shirt_version_display'], 'Player Issue')
        self.assertFalse(data['shirt_version_manual_value_recommended'])
        self.assertEqual(data['shirt_version_valuation_note'], '')

    def test_wishlist_serializer_adds_catalog_fields_without_changing_legacy_type(self):
        item = WishlistItem.objects.create(
            user=self.user,
            team=self.team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type,
        )

        data = WishlistItemSerializer(item).data

        self.assertEqual(data['kit_type'], 'Home')
        self.assertEqual(data['kit_type_id'], self.home_type.id)
        self.assertEqual(data['kit_type_slug'], 'home')
        self.assertEqual(data['kit_type_display'], 'Home')
        self.assertEqual(data['kit_type_canonical_code'], 'HOME')

    def test_options_keeps_legacy_arrays_and_adds_catalog_arrays(self):
        response = self.client.get(reverse('kit-options'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['technologies'],
            [
                {'value': 'PLAYER_ISSUE', 'label': 'Player Issue'},
                {'value': 'REPLICA', 'label': 'Replica'},
                {'value': 'MATCH_WORN', 'label': 'Match Worn'},
            ],
        )
        self.assertEqual(response.data['types'][0], {'value': 'Home', 'label': 'Home'})

        home_option = next(
            option for option in response.data['kit_types']
            if option['canonical_code'] == 'HOME'
        )
        self.assertEqual(
            home_option,
            {
                'id': self.home_type.id,
                'name': 'Home',
                'slug': 'home',
                'canonical_code': 'HOME',
                'category': 'outfield',
                'default_visibility': 'primary',
                'sort_order': 10,
            },
        )

        replica_option = next(
            option for option in response.data['shirt_versions']
            if option['code'] == 'REPLICA'
        )
        self.assertEqual(replica_option['id'], self.replica_version.id)
        self.assertEqual(replica_option['name'], 'Replica')
        self.assertIn('description', replica_option)
        self.assertFalse(replica_option['manual_value_recommended'])
        self.assertIn('valuation_note', replica_option)
        self.assertEqual(replica_option['sort_order'], 20)

    def test_phase_b_does_not_change_legacy_runtime_valuation(self):
        expected_values = {
            'REPLICA': Decimal('100.00'),
            'PLAYER_ISSUE': Decimal('150.00'),
            'MATCH_WORN': Decimal('500.00'),
        }

        for index, (technology, expected_value) in enumerate(expected_values.items()):
            kit = Kit.objects.create(
                team=self.team,
                season=f'201{index}/201{index + 1}',
                kit_type='Home',
                kit_type_ref=self.home_type,
                estimated_price=Decimal('100.00'),
            )
            user_kit = UserKit.objects.create(
                user=self.user,
                kit=kit,
                shirt_technology=technology,
                shirt_version=ShirtVersion.objects.get(code=technology),
                condition='VERY_GOOD',
                size='L',
            )

            self.assertEqual(user_kit.final_value, expected_value)


class ShirtVersionWriteAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='version_writer', password='password123')
        self.client.force_authenticate(user=self.user)
        self.team = Team.objects.create(name='Version Write FC', is_verified=True)

    def create_kit_with_price(self, season, kit_type='Home'):
        return Kit.objects.create(
            team=self.team,
            season=season,
            kit_type=kit_type,
            estimated_price=Decimal('100.00'),
        )

    def create_payload(self, kit, **overrides):
        payload = {
            'team_name': self.team.name,
            'season': kit.season,
            'kit_type': kit.kit_type,
            'size': 'L',
            'condition': 'VERY_GOOD',
        }
        payload.update(overrides)
        return payload

    def test_legacy_versions_keep_exact_existing_valuation(self):
        expected = {
            'REPLICA': Decimal('100.00'),
            'PLAYER_ISSUE': Decimal('150.00'),
            'MATCH_WORN': Decimal('500.00'),
        }

        for index, (code, final_value) in enumerate(expected.items()):
            kit = self.create_kit_with_price(f'202{index}/202{index + 1}')
            response = self.client.post(
                reverse('api-my-collection'),
                self.create_payload(kit, shirt_version_code=code),
                format='multipart',
            )

            self.assertEqual(response.status_code, 201)
            user_kit = UserKit.objects.get(pk=response.data['id'])
            self.assertEqual(user_kit.shirt_version.code, code)
            self.assertEqual(user_kit.shirt_technology, code)
            self.assertEqual(user_kit.final_value, final_value)
            self.assertEqual(response.data['shirt_version_code'], code)

    def test_new_version_uses_catalog_multiplier_and_neutral_legacy_fallback(self):
        kit = self.create_kit_with_price('2024/2025')

        response = self.client.post(
            reverse('api-my-collection'),
            self.create_payload(kit, shirt_version_code='MATCH_PREPARED'),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.get(pk=response.data['id'])
        self.assertEqual(user_kit.shirt_version.code, 'MATCH_PREPARED')
        self.assertEqual(user_kit.shirt_technology, 'REPLICA')
        self.assertEqual(user_kit.final_value, Decimal('100.00'))
        self.assertEqual(response.data['shirt_version_display'], 'Match Prepared')

    def test_shirt_version_id_is_accepted(self):
        kit = self.create_kit_with_price('2025/2026')
        sample = ShirtVersion.objects.get(code='SAMPLE')

        response = self.client.post(
            reverse('api-my-collection'),
            self.create_payload(kit, shirt_version_id=sample.id),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.get(pk=response.data['id'])
        self.assertEqual(user_kit.shirt_version, sample)
        self.assertEqual(user_kit.shirt_technology, 'REPLICA')
        self.assertEqual(user_kit.final_value, Decimal('100.00'))

    def test_manual_value_overrides_new_version_multiplier(self):
        kit = self.create_kit_with_price('2026/2027')

        response = self.client.post(
            reverse('api-my-collection'),
            self.create_payload(
                kit,
                shirt_version_code='PROTOTYPE',
                manual_value='321.45',
            ),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.get(pk=response.data['id'])
        self.assertEqual(user_kit.shirt_version.code, 'PROTOTYPE')
        self.assertEqual(user_kit.final_value, Decimal('321.45'))

    def test_updating_version_recalculates_value_and_syncs_legacy_code(self):
        kit = self.create_kit_with_price('2027/2028')
        user_kit = UserKit.objects.create(
            user=self.user,
            kit=kit,
            shirt_technology='REPLICA',
            shirt_version=ShirtVersion.objects.get(code='REPLICA'),
            condition='VERY_GOOD',
            size='L',
        )

        response = self.client.patch(
            reverse('api-my-collection-detail', args=[user_kit.id]),
            {'shirt_version_code': 'PLAYER_ISSUE'},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        user_kit.refresh_from_db()
        self.assertEqual(user_kit.shirt_version.code, 'PLAYER_ISSUE')
        self.assertEqual(user_kit.shirt_technology, 'PLAYER_ISSUE')
        self.assertEqual(user_kit.final_value, Decimal('150.00'))

    def test_updating_to_new_version_preserves_existing_legacy_code(self):
        kit = self.create_kit_with_price('2028/2029')
        user_kit = UserKit.objects.create(
            user=self.user,
            kit=kit,
            shirt_technology='PLAYER_ISSUE',
            shirt_version=ShirtVersion.objects.get(code='PLAYER_ISSUE'),
            condition='VERY_GOOD',
            size='L',
        )

        response = self.client.patch(
            reverse('api-my-collection-detail', args=[user_kit.id]),
            {'shirt_version_code': 'AUTHENTIC'},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        user_kit.refresh_from_db()
        self.assertEqual(user_kit.shirt_version.code, 'AUTHENTIC')
        self.assertEqual(user_kit.shirt_technology, 'PLAYER_ISSUE')
        self.assertEqual(user_kit.final_value, Decimal('100.00'))

    def test_legacy_technology_only_request_still_works_and_sets_version(self):
        kit = self.create_kit_with_price('2029/2030')

        response = self.client.post(
            reverse('api-my-collection'),
            self.create_payload(kit, shirt_technology='MATCH_WORN'),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.get(pk=response.data['id'])
        self.assertEqual(user_kit.shirt_technology, 'MATCH_WORN')
        self.assertEqual(user_kit.shirt_version.code, 'MATCH_WORN')
        self.assertEqual(user_kit.final_value, Decimal('500.00'))

    def test_inactive_version_is_rejected(self):
        kit = self.create_kit_with_price('2030/2031')
        sample = ShirtVersion.objects.get(code='SAMPLE')
        sample.is_active = False
        sample.save(update_fields=['is_active'])

        response = self.client.post(
            reverse('api-my-collection'),
            self.create_payload(kit, shirt_version_code='SAMPLE'),
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('shirt_version_code', response.data)


class KitTypeWriteAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='kit_type_writer', password='password123')
        self.client.force_authenticate(user=self.user)
        self.team = Team.objects.create(name='Dynamic Types FC', is_verified=True)

    def payload(self, **overrides):
        payload = {
            'team_name': self.team.name,
            'season': '2024/2025',
            'size': 'L',
            'condition': 'VERY_GOOD',
            'shirt_version_code': 'REPLICA',
        }
        payload.update(overrides)
        return payload

    def test_create_with_kit_type_id_sets_fk_and_legacy_display(self):
        anniversary = KitType.objects.get(canonical_code='ANNIVERSARY')

        response = self.client.post(
            reverse('api-my-collection'),
            self.payload(
                kit_type='Outdated client label',
                kit_type_id=anniversary.id,
            ),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.select_related('kit__kit_type_ref').get(pk=response.data['id'])
        self.assertEqual(user_kit.kit.kit_type_ref, anniversary)
        self.assertEqual(user_kit.kit.kit_type, 'Anniversary')
        self.assertEqual(response.data['kit']['kit_type_display'], 'Anniversary')

    def test_create_with_kit_type_slug_sets_fk_and_legacy_display(self):
        second_goalkeeper = KitType.objects.get(canonical_code='SECOND_GOALKEEPER')

        response = self.client.post(
            reverse('api-my-collection'),
            self.payload(kit_type_slug='second-goalkeeper'),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.select_related('kit__kit_type_ref').get(pk=response.data['id'])
        self.assertEqual(user_kit.kit.kit_type_ref, second_goalkeeper)
        self.assertEqual(user_kit.kit.kit_type, 'Second Goalkeeper')

    def test_legacy_kit_type_name_still_resolves(self):
        home = KitType.objects.get(canonical_code='HOME')

        response = self.client.post(
            reverse('api-my-collection'),
            self.payload(kit_type='Home'),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.select_related('kit__kit_type_ref').get(pk=response.data['id'])
        self.assertEqual(user_kit.kit.kit_type_ref, home)
        self.assertEqual(user_kit.kit.kit_type, 'Home')

    def test_goalkeeper_alias_resolves_to_canonical_type(self):
        response = self.client.post(
            reverse('api-my-collection'),
            self.payload(kit_type='GK'),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.select_related('kit__kit_type_ref').get(pk=response.data['id'])
        self.assertEqual(user_kit.kit.kit_type_ref.canonical_code, 'GOALKEEPER')
        self.assertEqual(user_kit.kit.kit_type, 'Goalkeeper')

    def test_special_edition_alias_resolves_to_canonical_type(self):
        response = self.client.post(
            reverse('api-my-collection'),
            self.payload(kit_type='Special Edition'),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.select_related('kit__kit_type_ref').get(pk=response.data['id'])
        self.assertEqual(user_kit.kit.kit_type_ref.canonical_code, 'SPECIAL')
        self.assertEqual(user_kit.kit.kit_type, 'Special')

    def test_update_with_dynamic_type_changes_fk_and_legacy_display(self):
        kit = Kit.objects.create(
            team=self.team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=KitType.objects.get(canonical_code='HOME'),
            estimated_price=Decimal('100.00'),
        )
        user_kit = UserKit.objects.create(
            user=self.user,
            kit=kit,
            shirt_technology='REPLICA',
            shirt_version=ShirtVersion.objects.get(code='REPLICA'),
            condition='VERY_GOOD',
            size='L',
        )
        pre_match = KitType.objects.get(canonical_code='PRE_MATCH')

        response = self.client.patch(
            reverse('api-my-collection-detail', args=[user_kit.id]),
            {
                'team_name': self.team.name,
                'season': '2024/2025',
                'kit_type': 'Pre-match',
                'kit_type_id': pre_match.id,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        user_kit.refresh_from_db()
        self.assertEqual(user_kit.kit.kit_type_ref, pre_match)
        self.assertEqual(user_kit.kit.kit_type, 'Pre-match')

    def test_create_with_custom_type_creates_pending_catalog_and_team_season_suggestion(self):
        response = self.client.post(
            reverse('api-my-collection'),
            self.payload(kit_type='Player Spec Tribute'),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        user_kit = UserKit.objects.select_related('kit__kit_type_ref').get(pk=response.data['id'])
        self.assertIsNotNone(user_kit.kit.kit_type_ref)
        self.assertEqual(user_kit.kit.kit_type_ref.name, 'Player Spec Tribute')
        self.assertEqual(user_kit.kit.kit_type_ref.status, KitType.STATUS_PENDING)
        self.assertEqual(user_kit.kit.kit_type, 'Player Spec Tribute')

        suggestion = TeamSeasonKitType.objects.get(
            team=self.team,
            season='2024/2025',
            kit_type=user_kit.kit.kit_type_ref,
        )
        self.assertEqual(suggestion.status, TeamSeasonKitType.STATUS_PENDING)
        self.assertEqual(suggestion.source, TeamSeasonKitType.SOURCE_UPLOAD)
        self.assertEqual(suggestion.created_by, self.user)

    def test_create_new_unverified_team_with_custom_type_defers_team_season_suggestion(self):
        response = self.client.post(
            reverse('api-my-collection'),
            self.payload(
                team_name='Fresh Upload United',
                kit_type='Tunnel Walk Anthem',
            ),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        team = Team.objects.get(name='Fresh Upload United')
        self.assertFalse(team.is_verified)
        self.assertFalse(TeamSeasonKitType.objects.filter(team=team).exists())

        user_kit = UserKit.objects.select_related('kit__kit_type_ref').get(pk=response.data['id'])
        self.assertEqual(user_kit.kit.team_id, team.id)
        self.assertIsNotNone(user_kit.kit.kit_type_ref)
        self.assertEqual(user_kit.kit.kit_type_ref.name, 'Tunnel Walk Anthem')
        self.assertEqual(user_kit.kit.kit_type, 'Tunnel Walk Anthem')

    def test_create_new_unverified_team_with_default_type_creates_no_team_season_row(self):
        response = self.client.post(
            reverse('api-my-collection'),
            self.payload(
                team_name='Default Type Wanderers',
                kit_type='Home',
            ),
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        team = Team.objects.get(name='Default Type Wanderers')
        self.assertFalse(team.is_verified)
        self.assertFalse(TeamSeasonKitType.objects.filter(team=team).exists())


class AdminKitTypeModerationAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff_user = User.objects.create_user(
            username='staff_moderator',
            password='password123',
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username='super_admin',
            email='super@example.com',
            password='password123',
        )
        self.moderator_user = User.objects.create_user(
            username='community_moderator',
            password='password123',
        )
        self.moderator_user.profile.is_moderator = True
        self.moderator_user.profile.save(update_fields=['is_moderator'])
        self.other_moderator_user = User.objects.create_user(
            username='second_moderator',
            password='password123',
        )
        self.other_moderator_user.profile.is_moderator = True
        self.other_moderator_user.profile.save(update_fields=['is_moderator'])
        self.regular_user = User.objects.create_user(
            username='regular_user',
            password='password123',
        )
        self.creator = User.objects.create_user(
            username='suggestion_creator',
            password='password123',
        )
        self.team = Team.objects.create(name='Moderation FC', is_verified=True)
        self.pending_type = KitType.objects.create(
            name='Player Spec Tribute',
            slug='player-spec-tribute',
            category=KitType.CATEGORY_OTHER,
            status=KitType.STATUS_PENDING,
            default_visibility=KitType.VISIBILITY_NONE,
            created_by=self.creator,
        )
        self.pending_suggestion = TeamSeasonKitType.objects.create(
            team=self.team,
            season='2024/2025',
            kit_type=self.pending_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )
        self.pending_kit = Kit.objects.create(
            team=self.team,
            season='2024/2025',
            kit_type='Player Spec Tribute',
            kit_type_ref=self.pending_type,
            estimated_price=Decimal('100.00'),
        )
        self.pending_userkit = UserKit.objects.create(
            user=self.creator,
            kit=self.pending_kit,
            shirt_technology='REPLICA',
            shirt_version=ShirtVersion.objects.get(code='REPLICA'),
            condition='VERY_GOOD',
            size='L',
        )
        UserKitImage.objects.create(
            user_kit=self.pending_userkit,
            image=SimpleUploadedFile('moderation-preview.jpg', b'preview', content_type='image/jpeg'),
            order=0,
        )
        self.home_type = KitType.objects.get(canonical_code='HOME')

    def approve(self, user=None):
        self.client.force_authenticate(user=user or self.staff_user)
        return self.client.post(
            reverse('admin-team-season-kit-type-approve', args=[self.pending_suggestion.id])
        )

    def reject(self, user=None):
        self.client.force_authenticate(user=user or self.staff_user)
        return self.client.post(
            reverse('admin-team-season-kit-type-reject', args=[self.pending_suggestion.id])
        )

    def merge(self, user=None, target_id=None):
        self.client.force_authenticate(user=user or self.staff_user)
        return self.client.post(
            reverse('admin-team-season-kit-type-merge', args=[self.pending_suggestion.id]),
            {'target_kit_type_id': target_id or self.home_type.id},
            format='json',
        )

    def undo_action(self, action_id, user=None):
        self.client.force_authenticate(user=user or self.staff_user)
        return self.client.post(
            reverse('admin-kit-type-moderation-action-undo', args=[action_id])
        )

    def test_anonymous_user_cannot_access_admin_suggestions(self):
        response = self.client.get(reverse('admin-kit-type-suggestions'))

        self.assertEqual(response.status_code, 401)

    def test_normal_authenticated_user_gets_403_for_admin_suggestions(self):
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get(reverse('admin-kit-type-suggestions'))

        self.assertEqual(response.status_code, 403)

    def test_moderator_can_list_pending_suggestions_with_context(self):
        self.client.force_authenticate(user=self.moderator_user)

        response = self.client.get(reverse('admin-kit-type-suggestions'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        suggestion = response.data[0]
        self.assertEqual(suggestion['id'], self.pending_suggestion.id)
        self.assertEqual(suggestion['team_id'], self.team.id)
        self.assertEqual(suggestion['team_name'], self.team.name)
        self.assertEqual(suggestion['season'], '2024/2025')
        self.assertEqual(suggestion['kit_type_id'], self.pending_type.id)
        self.assertEqual(suggestion['kit_type_name'], 'Player Spec Tribute')
        self.assertEqual(suggestion['kit_type_slug'], 'player-spec-tribute')
        self.assertEqual(suggestion['kit_type_status'], KitType.STATUS_PENDING)
        self.assertEqual(suggestion['team_season_status'], TeamSeasonKitType.STATUS_PENDING)
        self.assertEqual(suggestion['created_by_username'], self.creator.username)
        self.assertEqual(suggestion['upload_count'], 1)
        self.assertIsNotNone(suggestion['preview_image'])
        self.assertEqual(suggestion['example_source_userkit_id'], self.pending_userkit.id)
        self.assertIn('/history/team/moderation-fc/variants?', suggestion['museum_url'])

    def test_staff_user_can_list_pending_suggestions_with_context(self):
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get(reverse('admin-kit-type-suggestions'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        suggestion = response.data[0]
        self.assertEqual(suggestion['id'], self.pending_suggestion.id)
        self.assertEqual(suggestion['team_id'], self.team.id)
        self.assertEqual(suggestion['team_name'], self.team.name)
        self.assertEqual(suggestion['season'], '2024/2025')
        self.assertEqual(suggestion['kit_type_id'], self.pending_type.id)
        self.assertEqual(suggestion['kit_type_name'], 'Player Spec Tribute')
        self.assertEqual(suggestion['kit_type_slug'], 'player-spec-tribute')
        self.assertEqual(suggestion['kit_type_status'], KitType.STATUS_PENDING)
        self.assertEqual(suggestion['team_season_status'], TeamSeasonKitType.STATUS_PENDING)
        self.assertEqual(suggestion['created_by_username'], self.creator.username)
        self.assertEqual(suggestion['upload_count'], 1)
        self.assertIsNotNone(suggestion['preview_image'])
        self.assertEqual(suggestion['example_source_userkit_id'], self.pending_userkit.id)
        self.assertIn('/history/team/moderation-fc/variants?', suggestion['museum_url'])

    def test_superuser_can_list_pending_suggestions_with_context(self):
        self.client.force_authenticate(user=self.superuser)

        response = self.client.get(reverse('admin-kit-type-suggestions'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_pending_suggestions_for_unverified_teams_are_hidden_from_admin_queue(self):
        hidden_team = Team.objects.create(name='Hidden Queue FC', is_verified=False)
        hidden_suggestion = TeamSeasonKitType.objects.create(
            team=hidden_team,
            season='2024/2025',
            kit_type=self.pending_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )
        self.client.force_authenticate(user=self.moderator_user)

        response = self.client.get(reverse('admin-kit-type-suggestions'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data], [self.pending_suggestion.id])
        self.assertNotIn(hidden_suggestion.id, [row['id'] for row in response.data])

    def test_moderator_can_approve_pending_suggestion_and_pending_type(self):
        self.client.force_authenticate(user=self.moderator_user)

        response = self.client.post(
            reverse('admin-team-season-kit-type-approve', args=[self.pending_suggestion.id])
        )

        self.assertEqual(response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.pending_type.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_APPROVED)
        self.assertEqual(self.pending_suggestion.approved_by, self.moderator_user)
        self.assertIsNotNone(self.pending_suggestion.approved_at)
        self.assertEqual(self.pending_type.status, KitType.STATUS_APPROVED)
        self.assertEqual(self.pending_type.approved_by, self.moderator_user)
        self.assertIsNotNone(self.pending_type.approved_at)

    def test_staff_can_approve_pending_suggestion_and_pending_type(self):
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.post(
            reverse('admin-team-season-kit-type-approve', args=[self.pending_suggestion.id])
        )

        self.assertEqual(response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.pending_type.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_APPROVED)
        self.assertEqual(self.pending_suggestion.approved_by, self.staff_user)
        self.assertIsNotNone(self.pending_suggestion.approved_at)
        self.assertEqual(self.pending_type.status, KitType.STATUS_APPROVED)
        self.assertEqual(self.pending_type.approved_by, self.staff_user)
        self.assertIsNotNone(self.pending_type.approved_at)

    def test_superuser_can_approve_pending_suggestion_and_pending_type(self):
        self.client.force_authenticate(user=self.superuser)

        response = self.client.post(
            reverse('admin-team-season-kit-type-approve', args=[self.pending_suggestion.id])
        )

        self.assertEqual(response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.pending_type.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_APPROVED)
        self.assertEqual(self.pending_suggestion.approved_by, self.superuser)
        self.assertEqual(self.pending_type.status, KitType.STATUS_APPROVED)
        self.assertEqual(self.pending_type.approved_by, self.superuser)

    def test_normal_user_cannot_approve_pending_suggestion(self):
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.post(
            reverse('admin-team-season-kit-type-approve', args=[self.pending_suggestion.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_moderator_can_reject_pending_suggestion_without_deleting_uploads(self):
        self.client.force_authenticate(user=self.moderator_user)

        response = self.client.post(
            reverse('admin-team-season-kit-type-reject', args=[self.pending_suggestion.id])
        )

        self.assertEqual(response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_REJECTED)
        self.assertTrue(UserKit.objects.filter(pk=self.pending_userkit.id).exists())

    def test_staff_can_reject_pending_suggestion_without_deleting_uploads(self):
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.post(
            reverse('admin-team-season-kit-type-reject', args=[self.pending_suggestion.id])
        )

        self.assertEqual(response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_REJECTED)
        self.assertTrue(UserKit.objects.filter(pk=self.pending_userkit.id).exists())

    def test_superuser_can_reject_pending_suggestion_without_deleting_uploads(self):
        self.client.force_authenticate(user=self.superuser)

        response = self.client.post(
            reverse('admin-team-season-kit-type-reject', args=[self.pending_suggestion.id])
        )

        self.assertEqual(response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_REJECTED)
        self.assertTrue(UserKit.objects.filter(pk=self.pending_userkit.id).exists())

    def test_normal_user_cannot_reject_pending_suggestion(self):
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.post(
            reverse('admin-team-season-kit-type-reject', args=[self.pending_suggestion.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_staff_can_merge_pending_type_into_approved_type(self):
        existing_target = TeamSeasonKitType.objects.create(
            team=self.team,
            season='2024/2025',
            kit_type=self.home_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )
        other_team = Team.objects.create(name='Merge FC', is_verified=True)
        other_suggestion = TeamSeasonKitType.objects.create(
            team=other_team,
            season='2025/2026',
            kit_type=self.pending_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )
        other_kit = Kit.objects.create(
            team=other_team,
            season='2025/2026',
            kit_type='Player Spec Tribute',
            kit_type_ref=self.pending_type,
            estimated_price=Decimal('90.00'),
        )
        UserKit.objects.create(
            user=self.creator,
            kit=other_kit,
            shirt_technology='REPLICA',
            shirt_version=ShirtVersion.objects.get(code='REPLICA'),
            condition='VERY_GOOD',
            size='L',
        )
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.post(
            reverse('admin-team-season-kit-type-merge', args=[self.pending_suggestion.id]),
            {'target_kit_type_id': self.home_type.id},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.pending_type.refresh_from_db()
        self.pending_kit.refresh_from_db()
        other_kit.refresh_from_db()
        existing_target.refresh_from_db()
        other_suggestion.refresh_from_db()

        self.assertEqual(self.pending_kit.kit_type_ref, self.home_type)
        self.assertEqual(self.pending_kit.kit_type, self.home_type.name)
        self.assertEqual(other_kit.kit_type_ref, self.home_type)
        self.assertEqual(other_kit.kit_type, self.home_type.name)
        self.assertEqual(self.pending_type.status, KitType.STATUS_MERGED)
        self.assertEqual(self.pending_type.merged_into, self.home_type)
        self.assertFalse(TeamSeasonKitType.objects.filter(pk=self.pending_suggestion.id).exists())
        self.assertEqual(existing_target.status, TeamSeasonKitType.STATUS_APPROVED)
        self.assertEqual(other_suggestion.kit_type, self.home_type)
        self.assertTrue(
            KitTypeAlias.objects.filter(
                alias_normalized='player spec tribute',
                kit_type=self.home_type,
            ).exists()
        )

    def test_moderator_can_merge_pending_type_into_approved_type(self):
        existing_target = TeamSeasonKitType.objects.create(
            team=self.team,
            season='2024/2025',
            kit_type=self.home_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )
        other_team = Team.objects.create(name='Merge Moderator FC', is_verified=True)
        other_suggestion = TeamSeasonKitType.objects.create(
            team=other_team,
            season='2025/2026',
            kit_type=self.pending_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )
        other_kit = Kit.objects.create(
            team=other_team,
            season='2025/2026',
            kit_type='Player Spec Tribute',
            kit_type_ref=self.pending_type,
            estimated_price=Decimal('90.00'),
        )
        UserKit.objects.create(
            user=self.creator,
            kit=other_kit,
            shirt_technology='REPLICA',
            shirt_version=ShirtVersion.objects.get(code='REPLICA'),
            condition='VERY_GOOD',
            size='L',
        )
        self.client.force_authenticate(user=self.moderator_user)

        response = self.client.post(
            reverse('admin-team-season-kit-type-merge', args=[self.pending_suggestion.id]),
            {'target_kit_type_id': self.home_type.id},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.pending_type.refresh_from_db()
        self.pending_kit.refresh_from_db()
        other_kit.refresh_from_db()
        existing_target.refresh_from_db()
        other_suggestion.refresh_from_db()

        self.assertEqual(self.pending_kit.kit_type_ref, self.home_type)
        self.assertEqual(other_kit.kit_type_ref, self.home_type)
        self.assertEqual(self.pending_type.status, KitType.STATUS_MERGED)
        self.assertEqual(self.pending_type.merged_into, self.home_type)
        self.assertFalse(TeamSeasonKitType.objects.filter(pk=self.pending_suggestion.id).exists())
        self.assertEqual(existing_target.status, TeamSeasonKitType.STATUS_APPROVED)
        self.assertEqual(other_suggestion.kit_type, self.home_type)

    def test_superuser_can_merge_pending_type_into_approved_type(self):
        self.client.force_authenticate(user=self.superuser)

        response = self.client.post(
            reverse('admin-team-season-kit-type-merge', args=[self.pending_suggestion.id]),
            {'target_kit_type_id': self.home_type.id},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.pending_type.refresh_from_db()
        self.assertEqual(self.pending_type.status, KitType.STATUS_MERGED)
        self.assertEqual(self.pending_type.merged_into, self.home_type)

    def test_normal_user_cannot_merge_pending_type_into_approved_type(self):
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.post(
            reverse('admin-team-season-kit-type-merge', args=[self.pending_suggestion.id]),
            {'target_kit_type_id': self.home_type.id},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_current_user_includes_is_staff_flag(self):
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get(reverse('current-user'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_staff'])

    def test_current_user_includes_moderator_profile_flag(self):
        self.client.force_authenticate(user=self.moderator_user)

        response = self.client.get(reverse('current-user'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_staff'])
        self.assertTrue(response.data['profile']['is_moderator'])

    def test_anonymous_user_cannot_list_moderation_actions(self):
        response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(response.status_code, 401)

    def test_anonymous_user_cannot_undo_moderation_action(self):
        action = KitTypeModerationAction.objects.create(
            actor=self.staff_user,
            action_type=KitTypeModerationAction.ACTION_REJECT,
            team_season_kit_type=self.pending_suggestion,
            source_kit_type=self.pending_type,
        )

        response = self.client.post(
            reverse('admin-kit-type-moderation-action-undo', args=[action.id])
        )

        self.assertEqual(response.status_code, 401)

    def test_normal_user_gets_403_for_moderation_actions_list(self):
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(response.status_code, 403)

    def test_normal_user_gets_403_for_moderation_action_undo(self):
        approve_response = self.approve()
        action_id = approve_response.data['moderation_action_id']
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.post(
            reverse('admin-kit-type-moderation-action-undo', args=[action_id])
        )

        self.assertEqual(response.status_code, 403)

    def test_moderator_can_list_moderation_actions(self):
        self.approve(user=self.moderator_user)
        self.client.force_authenticate(user=self.moderator_user)

        response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['action_type'], KitTypeModerationAction.ACTION_APPROVE)
        self.assertTrue(response.data[0]['can_undo'])

    def test_moderator_can_see_other_moderators_actions_but_cannot_undo_them(self):
        response = self.approve(user=self.other_moderator_user)
        action_id = response.data['moderation_action_id']
        self.client.force_authenticate(user=self.moderator_user)

        list_response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]['id'], action_id)
        self.assertFalse(list_response.data[0]['can_undo'])

    def test_moderator_can_undo_their_own_approve_action(self):
        response = self.approve(user=self.moderator_user)
        action_id = response.data['moderation_action_id']

        undo_response = self.undo_action(action_id, user=self.moderator_user)

        self.assertEqual(undo_response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.pending_type.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_PENDING)
        self.assertEqual(self.pending_type.status, KitType.STATUS_PENDING)

    def test_moderator_can_undo_their_own_reject_action(self):
        response = self.reject(user=self.moderator_user)
        action_id = response.data['moderation_action_id']

        undo_response = self.undo_action(action_id, user=self.moderator_user)

        self.assertEqual(undo_response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_PENDING)

    def test_moderator_cannot_undo_another_moderators_approve_action(self):
        response = self.approve(user=self.moderator_user)
        action_id = response.data['moderation_action_id']
        self.client.force_authenticate(user=self.other_moderator_user)

        undo_response = self.client.post(
            reverse('admin-kit-type-moderation-action-undo', args=[action_id])
        )

        self.assertEqual(undo_response.status_code, 403)
        action = KitTypeModerationAction.objects.get(pk=action_id)
        self.assertIsNone(action.undone_at)
        self.assertIsNone(action.undone_by)
        self.pending_suggestion.refresh_from_db()
        self.pending_type.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_APPROVED)
        self.assertEqual(self.pending_type.status, KitType.STATUS_APPROVED)

    def test_moderator_cannot_undo_another_moderators_reject_action(self):
        response = self.reject(user=self.moderator_user)
        action_id = response.data['moderation_action_id']
        self.client.force_authenticate(user=self.other_moderator_user)

        undo_response = self.client.post(
            reverse('admin-kit-type-moderation-action-undo', args=[action_id])
        )

        self.assertEqual(undo_response.status_code, 403)
        action = KitTypeModerationAction.objects.get(pk=action_id)
        self.assertIsNone(action.undone_at)
        self.assertIsNone(action.undone_by)
        self.pending_suggestion.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_REJECTED)

    def test_staff_can_see_and_undo_another_moderators_action(self):
        response = self.approve(user=self.moderator_user)
        action_id = response.data['moderation_action_id']
        self.client.force_authenticate(user=self.staff_user)

        list_response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]['id'], action_id)
        self.assertTrue(list_response.data[0]['can_undo'])

        undo_response = self.undo_action(action_id, user=self.staff_user)
        self.assertEqual(undo_response.status_code, 200)

    def test_superuser_can_see_and_undo_another_moderators_action(self):
        response = self.approve(user=self.moderator_user)
        action_id = response.data['moderation_action_id']
        self.client.force_authenticate(user=self.superuser)

        list_response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]['id'], action_id)
        self.assertTrue(list_response.data[0]['can_undo'])

        undo_response = self.undo_action(action_id, user=self.superuser)
        self.assertEqual(undo_response.status_code, 200)

    def test_serializer_can_undo_true_for_own_reversible_action(self):
        response = self.approve(user=self.moderator_user)
        action_id = response.data['moderation_action_id']
        self.client.force_authenticate(user=self.moderator_user)

        list_response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]['id'], action_id)
        self.assertTrue(list_response.data[0]['can_undo'])

    def test_serializer_can_undo_false_for_other_moderators_action(self):
        response = self.approve(user=self.other_moderator_user)
        action_id = response.data['moderation_action_id']
        self.client.force_authenticate(user=self.moderator_user)

        list_response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]['id'], action_id)
        self.assertFalse(list_response.data[0]['can_undo'])

    def test_serializer_can_undo_true_for_staff_on_other_users_action(self):
        response = self.reject(user=self.moderator_user)
        action_id = response.data['moderation_action_id']
        self.client.force_authenticate(user=self.staff_user)

        list_response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]['id'], action_id)
        self.assertTrue(list_response.data[0]['can_undo'])

    def test_failed_foreign_moderator_undo_does_not_modify_audit_state(self):
        response = self.approve(user=self.moderator_user)
        action_id = response.data['moderation_action_id']
        self.pending_suggestion.refresh_from_db()
        self.pending_type.refresh_from_db()
        original_suggestion_status = self.pending_suggestion.status
        original_type_status = self.pending_type.status
        self.client.force_authenticate(user=self.other_moderator_user)

        undo_response = self.client.post(
            reverse('admin-kit-type-moderation-action-undo', args=[action_id])
        )

        self.assertEqual(undo_response.status_code, 403)
        action = KitTypeModerationAction.objects.get(pk=action_id)
        self.assertIsNone(action.undone_at)
        self.assertIsNone(action.undone_by)
        self.pending_suggestion.refresh_from_db()
        self.pending_type.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, original_suggestion_status)
        self.assertEqual(self.pending_type.status, original_type_status)

    def test_staff_and_superuser_can_undo_moderation_actions(self):
        approve_response = self.approve(user=self.staff_user)
        action_id = approve_response.data['moderation_action_id']

        staff_undo_response = self.undo_action(action_id, user=self.staff_user)
        self.assertEqual(staff_undo_response.status_code, 200)

        second_approve_response = self.approve(user=self.staff_user)
        second_action_id = second_approve_response.data['moderation_action_id']
        superuser_undo_response = self.undo_action(second_action_id, user=self.superuser)
        self.assertEqual(superuser_undo_response.status_code, 200)

    def test_approve_creates_moderation_action(self):
        response = self.approve()

        self.assertEqual(response.status_code, 200)
        action = KitTypeModerationAction.objects.get(pk=response.data['moderation_action_id'])
        self.assertEqual(action.action_type, KitTypeModerationAction.ACTION_APPROVE)
        self.assertTrue(action.is_reversible)
        self.assertEqual(action.team_name, self.team.name)
        self.assertEqual(action.season, '2024/2025')
        self.assertEqual(action.source_kit_type_name, self.pending_type.name)

    def test_undo_approve_restores_team_season_status(self):
        response = self.approve()
        action_id = response.data['moderation_action_id']

        undo_response = self.undo_action(action_id)

        self.assertEqual(undo_response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_PENDING)

    def test_undo_approve_restores_kit_type_status_if_approval_changed_it(self):
        response = self.approve()
        action_id = response.data['moderation_action_id']

        undo_response = self.undo_action(action_id)

        self.assertEqual(undo_response.status_code, 200)
        self.pending_type.refresh_from_db()
        self.assertEqual(self.pending_type.status, KitType.STATUS_PENDING)

    def test_undo_approve_restores_approved_by_and_approved_at_correctly(self):
        response = self.approve()
        action_id = response.data['moderation_action_id']

        self.assertIsNotNone(TeamSeasonKitType.objects.get(pk=self.pending_suggestion.id).approved_at)
        self.assertIsNotNone(KitType.objects.get(pk=self.pending_type.id).approved_at)

        undo_response = self.undo_action(action_id)

        self.assertEqual(undo_response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.pending_type.refresh_from_db()
        self.assertIsNone(self.pending_suggestion.approved_by)
        self.assertIsNone(self.pending_suggestion.approved_at)
        self.assertIsNone(self.pending_type.approved_by)
        self.assertIsNone(self.pending_type.approved_at)

    def test_undo_approve_returns_suggestion_to_pending_queue(self):
        response = self.approve()
        action_id = response.data['moderation_action_id']

        undo_response = self.undo_action(action_id)
        self.assertEqual(undo_response.status_code, 200)

        queue_response = self.client.get(reverse('admin-kit-type-suggestions'))
        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(len(queue_response.data), 1)
        self.assertEqual(queue_response.data[0]['id'], self.pending_suggestion.id)

    def test_undo_approve_removes_approved_museum_slot(self):
        response = self.approve()
        action_id = response.data['moderation_action_id']

        approved_response = self.client.get(
            reverse('approved-team-season-kit-types', args=[self.team.id])
        )
        self.assertEqual(len(approved_response.data), 1)

        undo_response = self.undo_action(action_id)
        self.assertEqual(undo_response.status_code, 200)

        approved_response = self.client.get(
            reverse('approved-team-season-kit-types', args=[self.team.id])
        )
        self.assertEqual(approved_response.data, [])

    def test_reject_creates_moderation_action(self):
        response = self.reject()

        self.assertEqual(response.status_code, 200)
        action = KitTypeModerationAction.objects.get(pk=response.data['moderation_action_id'])
        self.assertEqual(action.action_type, KitTypeModerationAction.ACTION_REJECT)
        self.assertTrue(action.is_reversible)

    def test_undo_reject_restores_previous_pending_status(self):
        response = self.reject()
        action_id = response.data['moderation_action_id']

        undo_response = self.undo_action(action_id)

        self.assertEqual(undo_response.status_code, 200)
        self.pending_suggestion.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_PENDING)

    def test_undo_reject_keeps_user_uploads_untouched(self):
        response = self.reject()
        action_id = response.data['moderation_action_id']

        undo_response = self.undo_action(action_id)

        self.assertEqual(undo_response.status_code, 200)
        self.assertTrue(UserKit.objects.filter(pk=self.pending_userkit.id).exists())

    def test_undo_reject_returns_suggestion_to_moderation_queue(self):
        response = self.reject()
        action_id = response.data['moderation_action_id']

        undo_response = self.undo_action(action_id)
        self.assertEqual(undo_response.status_code, 200)

        queue_response = self.client.get(reverse('admin-kit-type-suggestions'))
        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(len(queue_response.data), 1)

    def test_action_cannot_be_undone_twice(self):
        response = self.approve()
        action_id = response.data['moderation_action_id']

        first_undo = self.undo_action(action_id)
        second_undo = self.undo_action(action_id)

        self.assertEqual(first_undo.status_code, 200)
        self.assertEqual(second_undo.status_code, 409)

    def test_undone_action_records_undone_at_and_undone_by(self):
        response = self.approve(user=self.moderator_user)
        action_id = response.data['moderation_action_id']

        undo_response = self.undo_action(action_id, user=self.moderator_user)

        self.assertEqual(undo_response.status_code, 200)
        action = KitTypeModerationAction.objects.get(pk=action_id)
        self.assertIsNotNone(action.undone_at)
        self.assertEqual(action.undone_by, self.moderator_user)

    def test_undo_returns_409_when_object_state_changed_after_action(self):
        response = self.approve()
        action_id = response.data['moderation_action_id']
        self.pending_suggestion.refresh_from_db()
        self.pending_suggestion.status = TeamSeasonKitType.STATUS_REJECTED
        self.pending_suggestion.approved_by = None
        self.pending_suggestion.approved_at = None
        self.pending_suggestion.save(update_fields=['status', 'approved_by', 'approved_at'])

        undo_response = self.undo_action(action_id)

        self.assertEqual(undo_response.status_code, 409)
        self.pending_suggestion.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_REJECTED)

    def test_undo_conflict_does_not_partially_restore_data(self):
        response = self.approve()
        action_id = response.data['moderation_action_id']
        self.pending_type.refresh_from_db()
        self.pending_type.approved_by = self.superuser
        self.pending_type.save(update_fields=['approved_by'])

        undo_response = self.undo_action(action_id)

        self.assertEqual(undo_response.status_code, 409)
        self.pending_suggestion.refresh_from_db()
        self.pending_type.refresh_from_db()
        self.assertEqual(self.pending_suggestion.status, TeamSeasonKitType.STATUS_APPROVED)
        self.assertEqual(self.pending_type.status, KitType.STATUS_APPROVED)
        self.assertEqual(self.pending_type.approved_by, self.superuser)

    def test_merge_creates_non_reversible_audit_action(self):
        response = self.merge()

        self.assertEqual(response.status_code, 200)
        action = KitTypeModerationAction.objects.get(pk=response.data['moderation_action_id'])
        self.assertEqual(action.action_type, KitTypeModerationAction.ACTION_MERGE)
        self.assertFalse(action.is_reversible)
        self.assertEqual(action.undo_block_reason, 'Merge undo requires manual review.')

    def test_merge_action_list_reports_manual_review_reason(self):
        self.merge()
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get(reverse('admin-kit-type-moderation-actions'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['action_type'], KitTypeModerationAction.ACTION_MERGE)
        self.assertFalse(response.data[0]['can_undo'])
        self.assertEqual(response.data[0]['undo_block_reason'], 'Merge undo requires manual review.')

    def test_pending_suggestion_is_not_returned_by_approved_slots_endpoint(self):
        response = self.client.get(
            reverse('approved-team-season-kit-types', args=[self.team.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_rejected_suggestion_is_not_returned_by_approved_slots_endpoint(self):
        self.pending_suggestion.status = TeamSeasonKitType.STATUS_REJECTED
        self.pending_suggestion.save(update_fields=['status'])

        response = self.client.get(
            reverse('approved-team-season-kit-types', args=[self.team.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_approved_suggestion_is_returned_only_for_exact_team_and_season(self):
        self.pending_suggestion.status = TeamSeasonKitType.STATUS_APPROVED
        self.pending_suggestion.approved_by = self.staff_user
        self.pending_suggestion.approved_at = timezone.now()
        self.pending_suggestion.save(update_fields=['status', 'approved_by', 'approved_at'])
        self.pending_type.status = KitType.STATUS_APPROVED
        self.pending_type.approved_by = self.staff_user
        self.pending_type.approved_at = timezone.now()
        self.pending_type.save(update_fields=['status', 'approved_by', 'approved_at'])

        same_team_other_season = TeamSeasonKitType.objects.create(
            team=self.team,
            season='2025/2026',
            kit_type=self.pending_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )
        other_team = Team.objects.create(name='Other Moderation FC', is_verified=True)
        other_team_same_type = TeamSeasonKitType.objects.create(
            team=other_team,
            season='2024/2025',
            kit_type=self.pending_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )

        response = self.client.get(
            reverse('approved-team-season-kit-types', args=[self.team.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['season'], '2024/2025')
        self.assertEqual(response.data[0]['kit_type_id'], self.pending_type.id)
        self.assertNotIn(
            same_team_other_season.id,
            [row['id'] for row in response.data],
        )
        self.assertNotIn(
            other_team_same_type.id,
            [row['id'] for row in response.data],
        )

    def test_approving_one_team_season_slot_does_not_approve_other_seasons(self):
        self.pending_suggestion.status = TeamSeasonKitType.STATUS_APPROVED
        self.pending_suggestion.approved_by = self.staff_user
        self.pending_suggestion.approved_at = timezone.now()
        self.pending_suggestion.save(update_fields=['status', 'approved_by', 'approved_at'])
        self.pending_type.status = KitType.STATUS_APPROVED
        self.pending_type.approved_by = self.staff_user
        self.pending_type.approved_at = timezone.now()
        self.pending_type.save(update_fields=['status', 'approved_by', 'approved_at'])

        TeamSeasonKitType.objects.create(
            team=self.team,
            season='2025/2026',
            kit_type=self.pending_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )

        response = self.client.get(
            reverse('approved-team-season-kit-types', args=[self.team.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row['season'] for row in response.data],
            ['2024/2025'],
        )

    def test_approval_does_not_affect_another_team(self):
        self.pending_suggestion.status = TeamSeasonKitType.STATUS_APPROVED
        self.pending_suggestion.approved_by = self.staff_user
        self.pending_suggestion.approved_at = timezone.now()
        self.pending_suggestion.save(update_fields=['status', 'approved_by', 'approved_at'])
        self.pending_type.status = KitType.STATUS_APPROVED
        self.pending_type.approved_by = self.staff_user
        self.pending_type.approved_at = timezone.now()
        self.pending_type.save(update_fields=['status', 'approved_by', 'approved_at'])

        other_team = Team.objects.create(name='No Leakage FC', is_verified=True)
        TeamSeasonKitType.objects.create(
            team=other_team,
            season='2024/2025',
            kit_type=self.pending_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.creator,
        )

        response = self.client.get(
            reverse('approved-team-season-kit-types', args=[other_team.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_public_approved_team_season_slots_endpoint_returns_approved_rows(self):
        self.pending_suggestion.status = TeamSeasonKitType.STATUS_APPROVED
        self.pending_suggestion.approved_by = self.staff_user
        self.pending_suggestion.approved_at = timezone.now()
        self.pending_suggestion.save(update_fields=['status', 'approved_by', 'approved_at'])
        self.pending_type.status = KitType.STATUS_APPROVED
        self.pending_type.approved_by = self.staff_user
        self.pending_type.approved_at = timezone.now()
        self.pending_type.save(update_fields=['status', 'approved_by', 'approved_at'])

        response = self.client.get(
            reverse('approved-team-season-kit-types', args=[self.team.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['season'], '2024/2025')
        self.assertEqual(response.data[0]['kit_type_id'], self.pending_type.id)
        self.assertEqual(response.data[0]['kit_type_name'], self.pending_type.name)

    def test_public_approved_team_season_slots_endpoint_hides_unverified_teams(self):
        hidden_team = Team.objects.create(name='Hidden Museum FC', is_verified=False)
        self.pending_type.status = KitType.STATUS_APPROVED
        self.pending_type.approved_by = self.staff_user
        self.pending_type.approved_at = timezone.now()
        self.pending_type.save(update_fields=['status', 'approved_by', 'approved_at'])
        TeamSeasonKitType.objects.create(
            team=hidden_team,
            season='2024/2025',
            kit_type=self.pending_type,
            status=TeamSeasonKitType.STATUS_APPROVED,
            source=TeamSeasonKitType.SOURCE_MODERATOR,
            approved_by=self.staff_user,
            approved_at=timezone.now(),
        )

        response = self.client.get(
            reverse('approved-team-season-kit-types', args=[hidden_team.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])


class AdminTeamModerationAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff_user = User.objects.create_user(
            username='staff_team_moderator',
            password='password123',
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username='team_super_admin',
            email='teamsuper@example.com',
            password='password123',
        )
        self.moderator_user = User.objects.create_user(
            username='team_moderator',
            password='password123',
        )
        self.moderator_user.profile.is_moderator = True
        self.moderator_user.profile.save(update_fields=['is_moderator'])
        self.regular_user = User.objects.create_user(
            username='regular_team_user',
            password='password123',
        )
        self.owner = User.objects.create_user(username='team_owner', password='password123')
        self.other_owner = User.objects.create_user(username='team_other_owner', password='password123')
        self.reporter = User.objects.create_user(username='team_reporter', password='password123')
        self.liker = User.objects.create_user(username='team_liker', password='password123')
        self.favorite_user = User.objects.create_user(username='favorite_fan', password='password123')
        self.wishlist_owner = User.objects.create_user(username='wishlist_owner', password='password123')
        self.wishlist_duplicate_owner = User.objects.create_user(username='wishlist_duplicate_owner', password='password123')

        self.england = Country.objects.create(name='England', code='EN')
        self.spain = Country.objects.create(name='Spain', code='ES')
        self.inactive_country = Country.objects.create(name='Retired Nation', code='RN', is_active=False)
        self.premier_league = League.objects.create(name='Premier League', country=self.england)
        self.la_liga = League.objects.create(name='La Liga', country=self.spain)
        self.inactive_league = League.objects.create(
            name='Old First Division',
            country=self.england,
            is_active=False,
        )

        self.target_team = Team.objects.create(
            name='Arsenal F.C.',
            country=self.england,
            league=self.premier_league,
            is_verified=True,
        )
        self.similar_verified_team = Team.objects.create(
            name='Arsenal FC Women',
            country=self.england,
            league=self.premier_league,
            is_verified=True,
        )
        self.other_verified_team = Team.objects.create(
            name='Barcelona',
            country=self.spain,
            league=self.la_liga,
            is_verified=True,
        )
        self.source_team = Team.objects.create(name='Arsenal Legends', is_verified=False)
        self.unused_team = Team.objects.create(name='Unused Typo FC', is_verified=False)

        self.home_type = KitType.objects.get(canonical_code='HOME')
        self.away_type = KitType.objects.get(canonical_code='AWAY')

        self.target_duplicate_kit = Kit.objects.create(
            team=self.target_team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type,
            estimated_price=Decimal('0.00'),
        )
        self.source_duplicate_kit = Kit.objects.create(
            team=self.source_team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type,
            estimated_price=Decimal('120.00'),
        )
        self.source_unique_kit = Kit.objects.create(
            team=self.source_team,
            season='2023/2024',
            kit_type='Away',
            kit_type_ref=self.away_type,
            estimated_price=Decimal('85.00'),
        )

        self.duplicate_userkit = UserKit.objects.create(
            user=self.owner,
            kit=self.source_duplicate_kit,
            shirt_technology='REPLICA',
            shirt_version=ShirtVersion.objects.get(code='REPLICA'),
            condition='VERY_GOOD',
            size='L',
            private_note='Keep this note',
            manual_value=Decimal('333.00'),
        )
        self.unique_userkit = UserKit.objects.create(
            user=self.other_owner,
            kit=self.source_unique_kit,
            shirt_technology='PLAYER_ISSUE',
            shirt_version=ShirtVersion.objects.get(code='PLAYER_ISSUE'),
            condition='VERY_GOOD',
            size='M',
        )
        UserKitImage.objects.create(
            user_kit=self.duplicate_userkit,
            image=SimpleUploadedFile('team-preview.jpg', b'preview', content_type='image/jpeg'),
            order=0,
        )
        self.duplicate_userkit.likes.add(self.liker)
        self.comment = KitComment.objects.create(
            kit=self.duplicate_userkit,
            user=self.liker,
            body='Needs a review.',
        )
        self.report = KitReport.objects.create(
            kit=self.duplicate_userkit,
            reporter=self.reporter,
            reason='wrong_team',
            description='This should belong to Arsenal.',
        )

        self.target_duplicate_wishlist = WishlistItem.objects.create(
            user=self.wishlist_duplicate_owner,
            team=self.target_team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type,
        )
        self.source_unique_wishlist = WishlistItem.objects.create(
            user=self.wishlist_owner,
            team=self.source_team,
            season='2023/2024',
            kit_type='Away',
            kit_type_ref=self.away_type,
            source_userkit=self.unique_userkit,
        )
        self.source_duplicate_wishlist = WishlistItem.objects.create(
            user=self.wishlist_duplicate_owner,
            team=self.source_team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type,
            source_userkit=self.duplicate_userkit,
        )

        self.favorite_user.profile.favorite_team = self.source_team
        self.favorite_user.profile.save(update_fields=['favorite_team'])

        self.target_team_season = TeamSeasonKitType.objects.create(
            team=self.target_team,
            season='2024/2025',
            kit_type=self.home_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.owner,
        )
        self.source_duplicate_team_season = TeamSeasonKitType.objects.create(
            team=self.source_team,
            season='2024/2025',
            kit_type=self.home_type,
            status=TeamSeasonKitType.STATUS_APPROVED,
            source=TeamSeasonKitType.SOURCE_MODERATOR,
            created_by=self.owner,
            approved_by=self.staff_user,
            approved_at=timezone.now(),
        )
        self.source_unique_team_season = TeamSeasonKitType.objects.create(
            team=self.source_team,
            season='2023/2024',
            kit_type=self.away_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.other_owner,
        )

    def list_unverified(self, user=None, **params):
        self.client.force_authenticate(user=user) if user else self.client.force_authenticate(user=None)
        return self.client.get(reverse('admin-unverified-teams'), params)

    def approve_team(self, team_id, user=None, payload=None):
        self.client.force_authenticate(user=user or self.staff_user)
        default_payload = {
            'name': Team.objects.get(pk=team_id).name,
            'country_id': self.england.id,
        }
        if payload is not None:
            default_payload.update(payload)
        return self.client.post(
            reverse('admin-team-approve', args=[team_id]),
            default_payload,
            format='json',
        )

    def list_countries(self, user=None, **params):
        self.client.force_authenticate(user=user) if user else self.client.force_authenticate(user=None)
        return self.client.get(reverse('admin-countries'), params)

    def create_country(self, payload, user=None):
        self.client.force_authenticate(user=user or self.staff_user)
        return self.client.post(reverse('admin-countries'), payload, format='json')

    def list_leagues(self, user=None, **params):
        self.client.force_authenticate(user=user) if user else self.client.force_authenticate(user=None)
        return self.client.get(reverse('admin-leagues'), params)

    def create_league(self, payload, user=None):
        self.client.force_authenticate(user=user or self.staff_user)
        return self.client.post(reverse('admin-leagues'), payload, format='json')

    def merge_team(self, source_team_id, target_team_id, user=None):
        self.client.force_authenticate(user=user or self.staff_user)
        return self.client.post(
            reverse('admin-team-merge', args=[source_team_id]),
            {'target_team_id': target_team_id},
            format='json',
        )

    def reject_team(self, team_id, user=None):
        self.client.force_authenticate(user=user or self.staff_user)
        return self.client.post(reverse('admin-team-reject', args=[team_id]))

    def delete_team_content(self, team_id, payload=None, user=None):
        self.client.force_authenticate(user=user or self.staff_user)
        default_payload = {
            'confirmation': Team.objects.get(pk=team_id).name,
            'reason': 'spam',
            'note': '',
        }
        if payload is not None:
            default_payload.update(payload)
        return self.client.post(
            reverse('admin-team-delete-content', args=[team_id]),
            default_payload,
            format='json',
        )

    def test_anonymous_user_cannot_list_unverified_teams(self):
        response = self.client.get(reverse('admin-unverified-teams'))
        self.assertEqual(response.status_code, 401)

    def test_normal_user_cannot_list_unverified_teams(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(reverse('admin-unverified-teams'))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_and_normal_user_cannot_run_team_actions(self):
        anonymous_response = self.client.post(reverse('admin-team-approve', args=[self.source_team.id]))
        self.assertEqual(anonymous_response.status_code, 401)

        self.client.force_authenticate(user=self.regular_user)
        for route_name in ('admin-team-approve', 'admin-team-reject', 'admin-team-merge'):
            if route_name == 'admin-team-merge':
                response = self.client.post(
                    reverse(route_name, args=[self.source_team.id]),
                    {'target_team_id': self.target_team.id},
                    format='json',
                )
            else:
                response = self.client.post(reverse(route_name, args=[self.source_team.id]))
            self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(user=None)
        anonymous_delete_response = self.client.post(
            reverse('admin-team-delete-content', args=[self.source_team.id]),
            {'confirmation': self.source_team.name, 'reason': 'spam'},
            format='json',
        )
        self.assertEqual(anonymous_delete_response.status_code, 401)

        self.client.force_authenticate(user=self.regular_user)
        forbidden_delete_response = self.client.post(
            reverse('admin-team-delete-content', args=[self.source_team.id]),
            {'confirmation': self.source_team.name, 'reason': 'spam'},
            format='json',
        )
        self.assertEqual(forbidden_delete_response.status_code, 403)

    def test_anonymous_and_normal_user_cannot_access_country_or_league_admin_endpoints(self):
        self.assertEqual(self.client.get(reverse('admin-countries')).status_code, 401)
        self.assertEqual(self.client.get(reverse('admin-leagues')).status_code, 401)

        self.client.force_authenticate(user=self.regular_user)
        self.assertEqual(self.client.get(reverse('admin-countries')).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin-countries'), {'name': 'France', 'code': 'FR'}, format='json').status_code, 403)
        self.assertEqual(self.client.get(reverse('admin-leagues')).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin-leagues'), {'name': 'Ligue 1', 'country_id': self.england.id}, format='json').status_code, 403)

    def test_moderator_staff_and_superuser_can_list_unverified_teams(self):
        for user in (self.moderator_user, self.staff_user, self.superuser):
            self.client.force_authenticate(user=user)
            response = self.client.get(reverse('admin-unverified-teams'))
            self.assertEqual(response.status_code, 200)

    def test_moderator_staff_and_superuser_can_delete_unverified_team_content(self):
        for user in (self.moderator_user, self.staff_user, self.superuser):
            team = Team.objects.create(name=f'Deletable {user.username}', is_verified=False)
            kit = Kit.objects.create(
                team=team,
                season='2024/2025',
                kit_type='Home',
                kit_type_ref=self.home_type,
                estimated_price=Decimal('20.00'),
            )
            UserKit.objects.create(
                user=self.owner,
                kit=kit,
                shirt_technology='REPLICA',
                shirt_version=ShirtVersion.objects.get(code='REPLICA'),
                condition='VERY_GOOD',
                size='L',
            )
            response = self.delete_team_content(team.id, user=user)
            self.assertEqual(response.status_code, 200)

    def test_delete_team_content_rejects_bad_confirmation_invalid_reason_and_verified_teams(self):
        missing_confirmation = self.delete_team_content(
            self.source_team.id,
            payload={'confirmation': '', 'reason': 'spam'},
            user=self.moderator_user,
        )
        self.assertEqual(missing_confirmation.status_code, 400)
        self.assertEqual(missing_confirmation.data['code'], 'delete_confirmation_required')

        incorrect_confirmation = self.delete_team_content(
            self.source_team.id,
            payload={'confirmation': 'wrong name', 'reason': 'spam'},
            user=self.moderator_user,
        )
        self.assertEqual(incorrect_confirmation.status_code, 400)
        self.assertEqual(incorrect_confirmation.data['code'], 'delete_confirmation_required')

        invalid_reason = self.delete_team_content(
            self.source_team.id,
            payload={'confirmation': self.source_team.name, 'reason': 'bogus'},
            user=self.moderator_user,
        )
        self.assertEqual(invalid_reason.status_code, 400)
        self.assertIn('reason', invalid_reason.data)

        verified_delete = self.delete_team_content(
            self.target_team.id,
            payload={'confirmation': self.target_team.name, 'reason': 'spam'},
            user=self.moderator_user,
        )
        self.assertEqual(verified_delete.status_code, 409)
        self.assertEqual(verified_delete.data['code'], 'verified_team_delete_forbidden')

    def test_moderator_staff_and_superuser_can_list_and_create_countries_and_leagues(self):
        for user in (self.moderator_user, self.staff_user, self.superuser):
            self.assertEqual(self.list_countries(user=user).status_code, 200)
            self.assertEqual(self.list_leagues(user=user).status_code, 200)

        country_response = self.create_country({'name': 'France', 'code': 'fr'}, user=self.moderator_user)
        self.assertEqual(country_response.status_code, 201)
        country = Country.objects.get(pk=country_response.data['id'])
        self.assertEqual(country.code, 'FR')
        self.assertEqual(country.created_by_id, self.moderator_user.id)

        league_response = self.create_league(
            {'name': 'Ligue 1', 'country_id': country.id},
            user=self.staff_user,
        )
        self.assertEqual(league_response.status_code, 201)
        league = League.objects.get(pk=league_response.data['id'])
        self.assertEqual(league.created_by_id, self.staff_user.id)

    def test_unverified_teams_list_returns_only_unverified_rows_with_counts_preview_and_similarity(self):
        self.client.force_authenticate(user=self.moderator_user)

        response = self.client.get(reverse('admin-unverified-teams'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertFalse(response.data['has_more'])
        returned_ids = [team['id'] for team in response.data['results']]
        self.assertIn(self.source_team.id, returned_ids)
        self.assertIn(self.unused_team.id, returned_ids)
        self.assertNotIn(self.target_team.id, returned_ids)

        source_payload = next(team for team in response.data['results'] if team['id'] == self.source_team.id)
        unused_payload = next(team for team in response.data['results'] if team['id'] == self.unused_team.id)

        self.assertEqual(source_payload['slug'], 'arsenal-legends')
        self.assertEqual(source_payload['kits_count'], 2)
        self.assertEqual(source_payload['userkits_count'], 2)
        self.assertEqual(source_payload['unique_users_count'], 2)
        self.assertEqual(source_payload['wishlist_count'], 2)
        self.assertEqual(source_payload['favorite_team_count'], 1)
        self.assertEqual(source_payload['seasons'], ['2024/2025', '2023/2024'])
        self.assertIsNotNone(source_payload['preview_image'])
        self.assertFalse(source_payload['can_reject'])
        self.assertTrue(source_payload['reject_block_reason'])
        self.assertEqual(source_payload['usage']['approved_team_season_types'], 1)
        self.assertEqual(source_payload['usage']['pending_team_season_types'], 1)
        self.assertEqual(source_payload['usage']['rejected_team_season_types'], 0)
        self.assertTrue(any(team['id'] == self.target_team.id for team in source_payload['similar_verified_teams']))
        self.assertTrue(all(team['id'] != self.source_team.id for team in source_payload['similar_verified_teams']))
        self.assertIsNone(source_payload['country_id'])
        self.assertIsNone(source_payload['country_name'])
        self.assertIsNone(source_payload['country_code'])
        self.assertIsNone(source_payload['league_id'])
        self.assertIsNone(source_payload['league_name'])

        self.assertIsNone(unused_payload['preview_image'])
        self.assertTrue(unused_payload['can_reject'])
        self.assertEqual(unused_payload['reject_block_reason'], '')
        self.assertEqual(unused_payload['usage']['approved_team_season_types'], 0)
        self.assertEqual(unused_payload['usage']['pending_team_season_types'], 0)
        self.assertEqual(unused_payload['usage']['rejected_team_season_types'], 0)

    def test_unverified_queue_orders_oldest_first_with_id_tiebreak_and_limit(self):
        older_team = Team.objects.create(name='Older Queue FC', is_verified=False)
        newer_team = Team.objects.create(name='Newer Queue FC', is_verified=False)
        verified_team = Team.objects.create(name='Verified Queue FC', is_verified=True)
        same_name_team = Team.objects.create(name='Age Tie FC', is_verified=False)
        same_name_team_duplicate = Team.objects.create(name='Age Tie FC 2', is_verified=False)

        response = self.list_unverified(user=self.moderator_user, limit=50)

        self.assertEqual(response.status_code, 200)
        returned_ids = [team['id'] for team in response.data['results']]
        self.assertEqual(
            returned_ids,
            [
                self.source_team.id,
                self.unused_team.id,
                older_team.id,
                newer_team.id,
                same_name_team.id,
                same_name_team_duplicate.id,
            ],
        )
        self.assertFalse(response.data['has_more'])
        self.assertNotIn(verified_team.id, returned_ids)

        limited_response = self.list_unverified(user=self.moderator_user, limit=2)
        self.assertEqual(limited_response.status_code, 200)
        self.assertEqual(
            [team['id'] for team in limited_response.data['results']],
            [self.source_team.id, self.unused_team.id],
        )
        self.assertTrue(limited_response.data['has_more'])

    def test_country_list_returns_active_rows_by_default(self):
        response = self.list_countries(user=self.moderator_user)

        self.assertEqual(response.status_code, 200)
        country_ids = [row['id'] for row in response.data]
        self.assertIn(self.england.id, country_ids)
        self.assertIn(self.spain.id, country_ids)
        self.assertNotIn(self.inactive_country.id, country_ids)

        include_inactive_response = self.list_countries(user=self.moderator_user, include_inactive=1)
        self.assertIn(self.inactive_country.id, [row['id'] for row in include_inactive_response.data])

    def test_create_country_trims_uppercases_and_sets_creator(self):
        response = self.create_country(
            {'name': '  New   Zealand  ', 'code': ' nz '},
            user=self.moderator_user,
        )

        self.assertEqual(response.status_code, 201)
        country = Country.objects.get(pk=response.data['id'])
        self.assertEqual(country.name, 'New Zealand')
        self.assertEqual(country.code, 'NZ')
        self.assertEqual(country.created_by_id, self.moderator_user.id)
        self.assertTrue(country.is_active)

    def test_create_country_rejects_blank_name_blank_code_and_case_insensitive_duplicates(self):
        self.assertEqual(
            self.create_country({'name': '   ', 'code': 'EN'}, user=self.moderator_user).status_code,
            400,
        )
        self.assertEqual(
            self.create_country({'name': 'France', 'code': '   '}, user=self.moderator_user).status_code,
            400,
        )

        duplicate_name_response = self.create_country(
            {'name': ' england ', 'code': 'GB-ENG'},
            user=self.moderator_user,
        )
        self.assertEqual(duplicate_name_response.status_code, 409)
        self.assertEqual(duplicate_name_response.data['code'], 'country_name_conflict')
        self.assertEqual(duplicate_name_response.data['existing_country_id'], self.england.id)

        duplicate_code_response = self.create_country(
            {'name': 'Scotland', 'code': 'en'},
            user=self.moderator_user,
        )
        self.assertEqual(duplicate_code_response.status_code, 409)
        self.assertEqual(duplicate_code_response.data['code'], 'country_code_conflict')
        self.assertEqual(duplicate_code_response.data['existing_country_id'], self.england.id)

    def test_league_list_can_filter_by_country(self):
        response = self.list_leagues(user=self.moderator_user, country_id=self.england.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data], [self.premier_league.id])
        self.assertEqual(response.data[0]['country_id'], self.england.id)
        self.assertEqual(response.data[0]['country_code'], 'EN')

    def test_create_league_requires_active_country_and_normalized_name(self):
        blank_response = self.create_league(
            {'name': '   ', 'country_id': self.england.id},
            user=self.moderator_user,
        )
        self.assertEqual(blank_response.status_code, 400)

        inactive_country_response = self.create_league(
            {'name': 'Legacy League', 'country_id': self.inactive_country.id},
            user=self.moderator_user,
        )
        self.assertEqual(inactive_country_response.status_code, 400)

        response = self.create_league(
            {'name': '  FA   Cup  ', 'country_id': self.england.id},
            user=self.moderator_user,
        )
        self.assertEqual(response.status_code, 201)
        league = League.objects.get(pk=response.data['id'])
        self.assertEqual(league.name, 'FA Cup')
        self.assertEqual(league.created_by_id, self.moderator_user.id)
        self.assertTrue(league.is_active)

    def test_create_league_rejects_duplicates_and_retains_global_unique_limitation(self):
        duplicate_in_country_response = self.create_league(
            {'name': ' premier   league ', 'country_id': self.england.id},
            user=self.moderator_user,
        )
        self.assertEqual(duplicate_in_country_response.status_code, 409)
        self.assertEqual(duplicate_in_country_response.data['code'], 'league_name_conflict')
        self.assertEqual(duplicate_in_country_response.data['existing_league_id'], self.premier_league.id)

        duplicate_global_response = self.create_league(
            {'name': 'Premier League', 'country_id': self.spain.id},
            user=self.moderator_user,
        )
        self.assertEqual(duplicate_global_response.status_code, 409)
        self.assertEqual(duplicate_global_response.data['code'], 'league_global_name_conflict')
        self.assertEqual(duplicate_global_response.data['existing_league_id'], self.premier_league.id)

    def test_approve_requires_country(self):
        response = self.approve_team(
            self.source_team.id,
            user=self.moderator_user,
            payload={'name': 'Arsenal Legends', 'country_id': None},
        )
        self.assertEqual(response.status_code, 400)

    def test_approve_allows_null_or_omitted_league(self):
        null_response = self.approve_team(
            self.source_team.id,
            user=self.moderator_user,
            payload={
                'name': 'Arsenal Legends',
                'country_id': self.england.id,
                'league_id': None,
            },
        )
        self.assertEqual(null_response.status_code, 200)
        self.source_team.refresh_from_db()
        self.assertEqual(self.source_team.country_id, self.england.id)
        self.assertIsNone(self.source_team.league_id)

    def test_approve_rejects_league_country_mismatch_and_inactive_catalog_rows(self):
        mismatch_team = Team.objects.create(name='Mismatch FC', is_verified=False)
        mismatch_response = self.approve_team(
            mismatch_team.id,
            user=self.moderator_user,
            payload={
                'name': 'Mismatch FC',
                'country_id': self.england.id,
                'league_id': self.la_liga.id,
            },
        )
        self.assertEqual(mismatch_response.status_code, 400)
        self.assertEqual(mismatch_response.data['code'], 'league_country_mismatch')

        inactive_country_team = Team.objects.create(name='Inactive Country FC', is_verified=False)
        inactive_country_response = self.approve_team(
            inactive_country_team.id,
            user=self.moderator_user,
            payload={
                'name': 'Inactive Country FC',
                'country_id': self.inactive_country.id,
            },
        )
        self.assertEqual(inactive_country_response.status_code, 400)

        inactive_league_team = Team.objects.create(name='Inactive League FC', is_verified=False)
        inactive_league_response = self.approve_team(
            inactive_league_team.id,
            user=self.moderator_user,
            payload={
                'name': 'Inactive League FC',
                'country_id': self.england.id,
                'league_id': self.inactive_league.id,
            },
        )
        self.assertEqual(inactive_league_response.status_code, 400)

    def test_approve_marks_team_verified_and_preserves_references_and_audit(self):
        response = self.approve_team(
            self.source_team.id,
            user=self.moderator_user,
            payload={
                'name': '  Arsenal   Legends  ',
                'country_id': self.england.id,
                'league_id': self.premier_league.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.source_team.refresh_from_db()
        self.assertTrue(self.source_team.is_verified)
        self.assertEqual(self.source_team.name, 'Arsenal Legends')
        self.assertEqual(self.source_team.country_id, self.england.id)
        self.assertEqual(self.source_team.league_id, self.premier_league.id)
        self.assertEqual(Kit.objects.get(pk=self.source_duplicate_kit.id).team_id, self.source_team.id)
        self.assertEqual(UserKit.objects.get(pk=self.duplicate_userkit.id).kit_id, self.source_duplicate_kit.id)

        action = TeamModerationAction.objects.get(pk=response.data['moderation_action_id'])
        self.assertEqual(action.action_type, TeamModerationAction.ACTION_APPROVE)
        self.assertTrue(action.is_reversible)
        self.assertEqual(action.source_team_id_snapshot, self.source_team.id)
        self.assertEqual(action.previous_state['source_team']['country_id'], None)
        self.assertEqual(action.previous_state['source_team']['league_id'], None)
        self.assertEqual(action.resulting_state['source_team']['country_id'], self.england.id)
        self.assertEqual(action.resulting_state['source_team']['country_name'], 'England')
        self.assertEqual(action.resulting_state['source_team']['country_code'], 'EN')
        self.assertEqual(action.resulting_state['source_team']['league_id'], self.premier_league.id)
        self.assertEqual(action.resulting_state['source_team']['league_name'], 'Premier League')
        self.assertEqual(response.data['team']['id'], self.source_team.id)
        self.assertTrue(response.data['team']['is_verified'])
        self.assertEqual(response.data['team']['country_id'], self.england.id)
        self.assertEqual(response.data['team']['league_id'], self.premier_league.id)

    def test_approve_derives_deferred_suggestions_from_existing_custom_uploads(self):
        team = Team.objects.create(name='Deferred Custom FC', is_verified=False)
        custom_type = KitType.objects.create(
            name='Anniversary Night',
            slug='anniversary-night',
            category=KitType.CATEGORY_OTHER,
            status=KitType.STATUS_PENDING,
            default_visibility=KitType.VISIBILITY_NONE,
            created_by=self.owner,
        )
        first_kit = Kit.objects.create(
            team=team,
            season='2024/2025',
            kit_type=custom_type.name,
            kit_type_ref=custom_type,
            estimated_price=Decimal('100.00'),
        )
        second_kit = Kit.objects.create(
            team=team,
            season='2025/2026',
            kit_type=custom_type.name,
            kit_type_ref=custom_type,
            estimated_price=Decimal('105.00'),
        )
        default_kit = Kit.objects.create(
            team=team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type,
            estimated_price=Decimal('90.00'),
        )
        for kit, user in (
            (first_kit, self.owner),
            (first_kit, self.other_owner),
            (second_kit, self.other_owner),
            (default_kit, self.owner),
        ):
            UserKit.objects.create(
                user=user,
                kit=kit,
                shirt_technology='REPLICA',
                shirt_version=ShirtVersion.objects.get(code='REPLICA'),
                condition='VERY_GOOD',
                size='L',
            )

        response = self.approve_team(
            team.id,
            user=self.moderator_user,
            payload={'name': team.name, 'country_id': self.england.id},
        )

        self.assertEqual(response.status_code, 200)
        rows = list(TeamSeasonKitType.objects.filter(team=team).order_by('season'))
        self.assertEqual([(row.season, row.kit_type_id) for row in rows], [
            ('2024/2025', custom_type.id),
            ('2025/2026', custom_type.id),
        ])
        action = TeamModerationAction.objects.get(pk=response.data['moderation_action_id'])
        self.assertEqual(action.summary['created_team_season_suggestions'], 2)
        self.assertEqual(action.summary['reused_team_season_suggestions'], 0)

    def test_approve_reuses_existing_rows_without_reopening_rejected_or_downgrading_approved(self):
        team = Team.objects.create(name='Legacy Suggestion FC', is_verified=False)
        pending_type = KitType.objects.create(
            name='Pending Night',
            slug='pending-night',
            category=KitType.CATEGORY_OTHER,
            status=KitType.STATUS_PENDING,
            default_visibility=KitType.VISIBILITY_NONE,
            created_by=self.owner,
        )
        approved_type = KitType.objects.create(
            name='Approved Night',
            slug='approved-night',
            category=KitType.CATEGORY_OTHER,
            status=KitType.STATUS_APPROVED,
            default_visibility=KitType.VISIBILITY_NONE,
            approved_by=self.staff_user,
            approved_at=timezone.now(),
        )
        rejected_type = KitType.objects.create(
            name='Rejected Night',
            slug='rejected-night',
            category=KitType.CATEGORY_OTHER,
            status=KitType.STATUS_APPROVED,
            default_visibility=KitType.VISIBILITY_NONE,
            approved_by=self.staff_user,
            approved_at=timezone.now(),
        )
        for season, kit_type_ref, user in (
            ('2024/2025', pending_type, self.owner),
            ('2023/2024', approved_type, self.owner),
            ('2022/2023', rejected_type, self.other_owner),
        ):
            kit = Kit.objects.create(
                team=team,
                season=season,
                kit_type=kit_type_ref.name,
                kit_type_ref=kit_type_ref,
                estimated_price=Decimal('88.00'),
            )
            UserKit.objects.create(
                user=user,
                kit=kit,
                shirt_technology='REPLICA',
                shirt_version=ShirtVersion.objects.get(code='REPLICA'),
                condition='VERY_GOOD',
                size='L',
            )
        pending_row = TeamSeasonKitType.objects.create(
            team=team,
            season='2024/2025',
            kit_type=pending_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.owner,
        )
        approved_row = TeamSeasonKitType.objects.create(
            team=team,
            season='2023/2024',
            kit_type=approved_type,
            status=TeamSeasonKitType.STATUS_APPROVED,
            source=TeamSeasonKitType.SOURCE_MODERATOR,
            approved_by=self.staff_user,
            approved_at=timezone.now(),
        )
        rejected_row = TeamSeasonKitType.objects.create(
            team=team,
            season='2022/2023',
            kit_type=rejected_type,
            status=TeamSeasonKitType.STATUS_REJECTED,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.other_owner,
        )

        response = self.approve_team(
            team.id,
            user=self.moderator_user,
            payload={'name': team.name, 'country_id': self.england.id},
        )

        self.assertEqual(response.status_code, 200)
        pending_row.refresh_from_db()
        approved_row.refresh_from_db()
        rejected_row.refresh_from_db()
        self.assertEqual(pending_row.status, TeamSeasonKitType.STATUS_PENDING)
        self.assertEqual(approved_row.status, TeamSeasonKitType.STATUS_APPROVED)
        self.assertEqual(rejected_row.status, TeamSeasonKitType.STATUS_REJECTED)
        action = TeamModerationAction.objects.get(pk=response.data['moderation_action_id'])
        self.assertEqual(action.summary['created_team_season_suggestions'], 0)
        self.assertEqual(action.summary['reused_team_season_suggestions'], 3)

    def test_approve_makes_legacy_pending_suggestions_visible_in_queue_only_after_verification(self):
        team = Team.objects.create(name='Legacy Queue FC', is_verified=False)
        custom_type = KitType.objects.create(
            name='Queue Night',
            slug='queue-night',
            category=KitType.CATEGORY_OTHER,
            status=KitType.STATUS_PENDING,
            default_visibility=KitType.VISIBILITY_NONE,
            created_by=self.owner,
        )
        legacy_row = TeamSeasonKitType.objects.create(
            team=team,
            season='2024/2025',
            kit_type=custom_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.owner,
        )
        self.client.force_authenticate(user=self.moderator_user)
        hidden_response = self.client.get(reverse('admin-kit-type-suggestions'))
        self.assertEqual(hidden_response.status_code, 200)
        self.assertNotIn(legacy_row.id, [row['id'] for row in hidden_response.data])

        approve_response = self.approve_team(
            team.id,
            user=self.moderator_user,
            payload={'name': team.name, 'country_id': self.england.id},
        )

        self.assertEqual(approve_response.status_code, 200)
        visible_response = self.client.get(reverse('admin-kit-type-suggestions'))
        self.assertIn(legacy_row.id, [row['id'] for row in visible_response.data])

    def test_approve_rejects_case_insensitive_name_conflict(self):
        response = self.approve_team(
            self.source_team.id,
            user=self.moderator_user,
            payload={
                'name': ' arsenal f.c. ',
                'country_id': self.england.id,
                'league_id': self.premier_league.id,
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'team_name_conflict')
        self.assertEqual(response.data['existing_team_id'], self.target_team.id)

    def test_repeated_approval_returns_409(self):
        payload = {
            'name': 'Arsenal Legends',
            'country_id': self.england.id,
            'league_id': self.premier_league.id,
        }
        first = self.approve_team(self.source_team.id, payload=payload)
        second = self.approve_team(self.source_team.id, payload=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_merge_rejects_self_merge_unverified_target_and_verified_source(self):
        self.assertEqual(
            self.merge_team(self.source_team.id, self.source_team.id).status_code,
            400,
        )

        another_unverified = Team.objects.create(name='Arsenal Juniors', is_verified=False)
        self.assertEqual(
            self.merge_team(self.source_team.id, another_unverified.id).status_code,
            400,
        )

        verified_source = Team.objects.create(name='Verified Source FC', is_verified=True)
        self.assertEqual(
            self.merge_team(verified_source.id, self.target_team.id).status_code,
            409,
        )

    def test_merge_moves_non_conflicting_rows_reconciles_duplicates_and_preserves_user_content(self):
        snapshots_before = CollectionValueSnapshot.objects.count()
        duplicate_userkit_value = UserKit.objects.get(pk=self.duplicate_userkit.id).final_value

        response = self.merge_team(self.source_team.id, self.target_team.id, user=self.moderator_user)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Team.objects.filter(pk=self.source_team.id).exists())

        self.duplicate_userkit.refresh_from_db()
        self.unique_userkit.refresh_from_db()
        self.target_duplicate_kit.refresh_from_db()
        self.target_team_season.refresh_from_db()

        self.assertEqual(self.duplicate_userkit.kit_id, self.target_duplicate_kit.id)
        self.assertEqual(self.unique_userkit.kit.team_id, self.target_team.id)
        self.assertFalse(Kit.objects.filter(pk=self.source_duplicate_kit.id).exists())
        self.assertEqual(self.target_duplicate_kit.estimated_price, Decimal('120.00'))
        self.assertTrue(UserKitImage.objects.filter(user_kit=self.duplicate_userkit).exists())
        self.assertTrue(KitComment.objects.filter(pk=self.comment.id, kit=self.duplicate_userkit).exists())
        self.assertTrue(KitReport.objects.filter(pk=self.report.id, kit=self.duplicate_userkit).exists())
        self.assertEqual(self.duplicate_userkit.likes.count(), 1)
        self.assertEqual(self.duplicate_userkit.private_note, 'Keep this note')
        self.assertEqual(self.duplicate_userkit.final_value, duplicate_userkit_value)
        self.assertEqual(CollectionValueSnapshot.objects.count(), snapshots_before)

        self.assertEqual(WishlistItem.objects.filter(team=self.target_team).count(), 2)
        self.assertFalse(WishlistItem.objects.filter(pk=self.source_duplicate_wishlist.id).exists())
        kept_wishlist = WishlistItem.objects.get(pk=self.target_duplicate_wishlist.id)
        self.assertEqual(kept_wishlist.source_userkit_id, self.duplicate_userkit.id)
        moved_wishlist = WishlistItem.objects.get(pk=self.source_unique_wishlist.id)
        self.assertEqual(moved_wishlist.team_id, self.target_team.id)

        self.favorite_user.profile.refresh_from_db()
        self.assertEqual(self.favorite_user.profile.favorite_team_id, self.target_team.id)

        self.assertEqual(self.target_team_season.status, TeamSeasonKitType.STATUS_APPROVED)
        self.assertEqual(self.target_team_season.approved_by_id, self.staff_user.id)
        self.assertFalse(TeamSeasonKitType.objects.filter(pk=self.source_duplicate_team_season.id).exists())
        self.source_unique_team_season.refresh_from_db()
        self.assertEqual(self.source_unique_team_season.team_id, self.target_team.id)

        action = TeamModerationAction.objects.get(pk=response.data['moderation_action_id'])
        self.assertEqual(action.action_type, TeamModerationAction.ACTION_MERGE)
        self.assertFalse(action.is_reversible)
        self.assertEqual(action.undo_block_reason, 'Team merge undo requires manual review.')
        self.assertEqual(self.target_team.name, 'Arsenal F.C.')
        self.assertEqual(self.target_team.country_id, self.england.id)
        self.assertEqual(self.target_team.league_id, self.premier_league.id)
        self.assertEqual(response.data['merged_duplicate_kits'], 1)
        self.assertEqual(response.data['moved_userkits'], 1)
        self.assertEqual(response.data['deduplicated_wishlist_items'], 1)
        self.assertEqual(response.data['target_team']['country_id'], self.england.id)
        self.assertEqual(response.data['target_team']['league_id'], self.premier_league.id)

    def test_team_merge_is_atomic_when_a_later_step_fails(self):
        with patch('kits.team_moderation.reconcile_wishlist_items', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.merge_team(self.source_team.id, self.target_team.id)

        self.assertTrue(Team.objects.filter(pk=self.source_team.id).exists())
        self.source_duplicate_kit.refresh_from_db()
        self.source_unique_kit.refresh_from_db()
        self.duplicate_userkit.refresh_from_db()
        self.assertEqual(self.source_duplicate_kit.team_id, self.source_team.id)
        self.assertEqual(self.source_unique_kit.team_id, self.source_team.id)
        self.assertEqual(self.duplicate_userkit.kit_id, self.source_duplicate_kit.id)
        self.assertFalse(TeamModerationAction.objects.filter(action_type=TeamModerationAction.ACTION_MERGE).exists())

    def test_team_approval_is_atomic_when_suggestion_backfill_fails(self):
        team = Team.objects.create(name='Atomic Approval FC', is_verified=False)

        with patch('kits.team_moderation.create_team_season_suggestions_from_existing_kits', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.approve_team(
                    team.id,
                    user=self.moderator_user,
                    payload={'name': team.name, 'country_id': self.england.id},
                )

        team.refresh_from_db()
        self.assertFalse(team.is_verified)
        self.assertFalse(TeamModerationAction.objects.filter(source_team_id_snapshot=team.id).exists())

    def test_merge_creates_missing_suggestions_for_custom_uploads_under_verified_target(self):
        source_team = Team.objects.create(name='Merge Source Custom FC', is_verified=False)
        custom_type = KitType.objects.create(
            name='Merge Night',
            slug='merge-night',
            category=KitType.CATEGORY_OTHER,
            status=KitType.STATUS_PENDING,
            default_visibility=KitType.VISIBILITY_NONE,
            created_by=self.owner,
        )
        custom_kit = Kit.objects.create(
            team=source_team,
            season='2024/2025',
            kit_type=custom_type.name,
            kit_type_ref=custom_type,
            estimated_price=Decimal('99.00'),
        )
        UserKit.objects.create(
            user=self.owner,
            kit=custom_kit,
            shirt_technology='REPLICA',
            shirt_version=ShirtVersion.objects.get(code='REPLICA'),
            condition='VERY_GOOD',
            size='L',
        )

        response = self.merge_team(source_team.id, self.target_team.id, user=self.moderator_user)

        self.assertEqual(response.status_code, 200)
        suggestion = TeamSeasonKitType.objects.get(
            team=self.target_team,
            season='2024/2025',
            kit_type=custom_type,
        )
        self.assertEqual(suggestion.status, TeamSeasonKitType.STATUS_PENDING)
        self.assertFalse(TeamSeasonKitType.objects.filter(team_id=source_team.id).exists())
        self.assertEqual(response.data['created_team_season_suggestions'], 1)
        self.assertEqual(response.data['reused_team_season_suggestions'], 0)

    def test_merge_keeps_existing_rejected_target_suggestion_closed(self):
        source_team = Team.objects.create(name='Merge Source Rejected FC', is_verified=False)
        custom_type = KitType.objects.create(
            name='Rejected Merge Night',
            slug='rejected-merge-night',
            category=KitType.CATEGORY_OTHER,
            status=KitType.STATUS_PENDING,
            default_visibility=KitType.VISIBILITY_NONE,
            created_by=self.owner,
        )
        Kit.objects.create(
            team=source_team,
            season='2024/2025',
            kit_type=custom_type.name,
            kit_type_ref=custom_type,
            estimated_price=Decimal('101.00'),
        )
        target_row = TeamSeasonKitType.objects.create(
            team=self.target_team,
            season='2024/2025',
            kit_type=custom_type,
            status=TeamSeasonKitType.STATUS_REJECTED,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.owner,
        )

        response = self.merge_team(source_team.id, self.target_team.id, user=self.moderator_user)

        self.assertEqual(response.status_code, 200)
        target_row.refresh_from_db()
        self.assertEqual(target_row.status, TeamSeasonKitType.STATUS_REJECTED)
        self.assertEqual(
            TeamSeasonKitType.objects.filter(
                team=self.target_team,
                season='2024/2025',
                kit_type=custom_type,
            ).count(),
            1,
        )
        self.assertEqual(response.data['created_team_season_suggestions'], 0)
        self.assertEqual(response.data['reused_team_season_suggestions'], 1)

    def test_reject_deletes_unused_team_and_creates_audit_action(self):
        response = self.reject_team(self.unused_team.id, user=self.moderator_user)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Team.objects.filter(pk=self.unused_team.id).exists())
        action = TeamModerationAction.objects.get(pk=response.data['moderation_action_id'])
        self.assertEqual(action.action_type, TeamModerationAction.ACTION_REJECT)
        self.assertFalse(action.is_reversible)

    def test_delete_team_content_removes_associated_content_and_audits_summary(self):
        duplicate_like_notification = Notification.objects.create(
            recipient=self.owner,
            actor=self.liker,
            type='kit_like',
            kit=self.duplicate_userkit,
        )
        comment_notification = Notification.objects.create(
            recipient=self.owner,
            actor=self.liker,
            type='kit_comment',
            comment=self.comment,
        )
        comment_like = KitCommentLike.objects.create(comment=self.comment, user=self.owner)
        TeamSeasonKitType.objects.create(
            team=self.source_team,
            season='2022/2023',
            kit_type=self.home_type,
            status=TeamSeasonKitType.STATUS_REJECTED,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.owner,
        )
        owner_initial_snapshot = CollectionValueSnapshot.objects.create(
            user=self.owner,
            total_value=Decimal('333.00'),
            kits_count=1,
            reason=CollectionValueSnapshot.REASON_INITIAL,
        )
        other_owner_initial_snapshot = CollectionValueSnapshot.objects.create(
            user=self.other_owner,
            total_value=Decimal('0.00'),
            kits_count=1,
            reason=CollectionValueSnapshot.REASON_INITIAL,
        )

        response = self.delete_team_content(
            self.source_team.id,
            payload={
                'confirmation': self.source_team.name,
                'reason': 'offensive_name',
                'note': 'Obvious spam team name.',
            },
            user=self.moderator_user,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Team.objects.filter(pk=self.source_team.id).exists())
        self.assertFalse(Kit.objects.filter(pk=self.source_duplicate_kit.id).exists())
        self.assertFalse(Kit.objects.filter(pk=self.source_unique_kit.id).exists())
        self.assertFalse(UserKit.objects.filter(pk=self.duplicate_userkit.id).exists())
        self.assertFalse(UserKit.objects.filter(pk=self.unique_userkit.id).exists())
        self.assertFalse(UserKitImage.objects.filter(user_kit_id__in=[self.duplicate_userkit.id, self.unique_userkit.id]).exists())
        self.assertFalse(KitComment.objects.filter(pk=self.comment.id).exists())
        self.assertFalse(KitCommentLike.objects.filter(pk=comment_like.id).exists())
        self.assertFalse(Notification.objects.filter(pk=duplicate_like_notification.id).exists())
        self.assertFalse(Notification.objects.filter(pk=comment_notification.id).exists())
        self.assertFalse(KitReport.objects.filter(pk=self.report.id).exists())
        self.assertFalse(WishlistItem.objects.filter(team_id=self.source_team.id).exists())
        self.favorite_user.profile.refresh_from_db()
        self.assertIsNone(self.favorite_user.profile.favorite_team_id)
        self.assertFalse(TeamSeasonKitType.objects.filter(team=self.source_team).exists())
        self.assertTrue(KitType.objects.filter(pk=self.home_type.id).exists())
        self.assertTrue(KitType.objects.filter(pk=self.away_type.id).exists())
        self.assertTrue(User.objects.filter(pk=self.owner.id).exists())
        self.assertTrue(owner_initial_snapshot.pk)
        self.assertTrue(other_owner_initial_snapshot.pk)

        owner_snapshots = list(self.owner.collection_value_snapshots.order_by('id'))
        other_owner_snapshots = list(self.other_owner.collection_value_snapshots.order_by('id'))
        self.assertEqual(len(owner_snapshots), 2)
        self.assertEqual(len(other_owner_snapshots), 2)
        self.assertEqual(owner_snapshots[-1].reason, CollectionValueSnapshot.REASON_KIT_REMOVED)
        self.assertEqual(other_owner_snapshots[-1].reason, CollectionValueSnapshot.REASON_KIT_REMOVED)
        self.assertEqual(owner_snapshots[-1].kits_count, 0)
        self.assertEqual(other_owner_snapshots[-1].kits_count, 0)

        action = TeamModerationAction.objects.get(pk=response.data['moderation_action_id'])
        self.assertEqual(action.action_type, TeamModerationAction.ACTION_DELETE_CONTENT)
        self.assertFalse(action.is_reversible)
        self.assertEqual(action.undo_block_reason, 'Destructive team deletion cannot be automatically undone.')
        self.assertEqual(action.source_team_id_snapshot, self.source_team.id)
        self.assertEqual(action.summary['reason'], 'offensive_name')
        self.assertEqual(action.summary['note'], 'Obvious spam team name.')
        self.assertEqual(action.summary['deleted_kits'], 2)
        self.assertEqual(action.summary['deleted_userkits'], 2)
        self.assertEqual(action.summary['affected_users'], 2)
        self.assertEqual(action.summary['deleted_images'], 1)
        self.assertEqual(action.summary['deleted_comments'], 1)
        self.assertEqual(action.summary['deleted_comment_likes'], 1)
        self.assertEqual(action.summary['deleted_kit_likes'], 1)
        self.assertEqual(action.summary['deleted_reports'], 1)
        self.assertEqual(action.summary['deleted_notifications'], 2)
        self.assertEqual(action.summary['deleted_wishlist_items'], 2)
        self.assertEqual(action.summary['cleared_favorite_profiles'], 1)
        self.assertEqual(action.summary['deleted_team_season_types'], 3)
        self.assertEqual(action.summary['collection_snapshot_reason'], CollectionValueSnapshot.REASON_KIT_REMOVED)
        self.assertEqual(len(action.summary['report_snapshots']), 1)
        self.assertEqual(action.summary['report_snapshots'][0]['id'], self.report.id)
        self.assertNotIn('private_note', action.summary)
        self.assertEqual(response.data['summary']['deleted_userkits'], 2)

    def test_delete_team_content_is_atomic_when_snapshot_recording_fails(self):
        with patch(
            'kits.team_moderation.record_collection_value_snapshot',
            side_effect=[None, RuntimeError('snapshot failure')],
        ):
            with self.assertRaises(RuntimeError):
                self.delete_team_content(
                    self.source_team.id,
                    payload={
                        'confirmation': self.source_team.name,
                        'reason': 'spam',
                    },
                    user=self.moderator_user,
                )

        self.assertTrue(Team.objects.filter(pk=self.source_team.id).exists())
        self.assertTrue(Kit.objects.filter(pk=self.source_duplicate_kit.id).exists())
        self.assertTrue(UserKit.objects.filter(pk=self.duplicate_userkit.id).exists())
        self.assertTrue(WishlistItem.objects.filter(pk=self.source_unique_wishlist.id).exists())
        self.favorite_user.profile.refresh_from_db()
        self.assertEqual(self.favorite_user.profile.favorite_team_id, self.source_team.id)
        self.assertTrue(TeamSeasonKitType.objects.filter(pk=self.source_duplicate_team_season.id).exists())
        self.assertFalse(TeamModerationAction.objects.filter(action_type=TeamModerationAction.ACTION_DELETE_CONTENT).exists())

    def test_reject_blocks_used_team_with_usage_counts_and_preserves_content(self):
        response = self.reject_team(self.source_team.id)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'team_in_use')
        self.assertEqual(response.data['usage']['kits'], 2)
        self.assertEqual(response.data['usage']['userkits'], 2)
        self.assertEqual(response.data['usage']['wishlist_items'], 2)
        self.assertEqual(response.data['usage']['favorite_profiles'], 1)
        self.assertTrue(Team.objects.filter(pk=self.source_team.id).exists())
        self.assertTrue(UserKit.objects.filter(pk=self.duplicate_userkit.id).exists())
        self.assertFalse(TeamModerationAction.objects.filter(action_type=TeamModerationAction.ACTION_REJECT, source_team_id_snapshot=self.source_team.id).exists())

    def test_team_serializer_keeps_legacy_league_id_and_adds_country_metadata(self):
        serialized = TeamSerializer(self.target_team).data

        self.assertEqual(serialized['league'], self.premier_league.id)
        self.assertEqual(serialized['league_id'], self.premier_league.id)
        self.assertEqual(serialized['league_name'], 'Premier League')
        self.assertEqual(serialized['country_id'], self.england.id)
        self.assertEqual(serialized['country_name'], 'England')
        self.assertEqual(serialized['country_code'], 'EN')

    def test_public_country_and_league_endpoints_remain_compatible_with_additive_fields(self):
        countries_response = self.client.get(reverse('country-list'))
        leagues_response = self.client.get(reverse('league-list'))
        teams_response = self.client.get(reverse('teams-by-league', args=[self.premier_league.id]))

        self.assertEqual(countries_response.status_code, 200)
        self.assertEqual(leagues_response.status_code, 200)
        self.assertEqual(teams_response.status_code, 200)
        self.assertTrue(any(item['id'] == self.england.id and item['code'] == 'EN' for item in countries_response.data))
        premier_payload = next(item for item in leagues_response.data if item['id'] == self.premier_league.id)
        self.assertEqual(premier_payload['country']['id'], self.england.id)
        self.assertEqual(premier_payload['country']['code'], 'EN')
        team_payload = next(item for item in teams_response.data if item['id'] == self.target_team.id)
        self.assertEqual(team_payload['league'], self.premier_league.id)
        self.assertEqual(team_payload['country_id'], self.england.id)

    def test_reject_blocks_real_userkit_usage_with_concise_reason(self):
        team = Team.objects.create(name='Upload Block FC', is_verified=False)
        kit = Kit.objects.create(
            team=team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type,
            estimated_price=Decimal('90.00'),
        )
        UserKit.objects.create(
            user=self.owner,
            kit=kit,
            shirt_technology='REPLICA',
            shirt_version=ShirtVersion.objects.get(code='REPLICA'),
            condition='VERY_GOOD',
            size='L',
        )

        response = self.reject_team(team.id, user=self.moderator_user)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'team_in_use')
        self.assertEqual(response.data['detail'], '1 upload still uses this team.')
        self.assertEqual(response.data['usage']['userkits'], 1)
        self.assertEqual(response.data['usage']['orphan_kits'], 0)

    def test_wishlist_favorite_rows_block_rejection_and_stale_pending_team_season_rows_can_be_rejected(self):
        wishlist_team = Team.objects.create(name='Wishlist Block FC', is_verified=False)
        WishlistItem.objects.create(
            user=self.wishlist_owner,
            team=wishlist_team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type,
        )
        wishlist_response = self.reject_team(wishlist_team.id, user=self.moderator_user)
        self.assertEqual(wishlist_response.status_code, 409)
        self.assertEqual(wishlist_response.data['detail'], '1 wishlist item still uses this team.')

        favorite_team = Team.objects.create(name='Favorite Block FC', is_verified=False)
        self.favorite_user.profile.favorite_team = favorite_team
        self.favorite_user.profile.save(update_fields=['favorite_team'])
        favorite_response = self.reject_team(favorite_team.id, user=self.moderator_user)
        self.assertEqual(favorite_response.status_code, 409)
        self.assertEqual(favorite_response.data['detail'], '1 profile still favorites this team.')

        season_team = Team.objects.create(name='Season Block FC', is_verified=False)
        TeamSeasonKitType.objects.create(
            team=season_team,
            season='2024/2025',
            kit_type=self.home_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.owner,
        )
        season_response = self.reject_team(season_team.id, user=self.moderator_user)
        self.assertEqual(season_response.status_code, 200)
        self.assertFalse(Team.objects.filter(pk=season_team.id).exists())

    def test_approved_team_season_rows_use_approved_blocker_reason(self):
        team = Team.objects.create(name='Approved Slot FC', is_verified=False)
        TeamSeasonKitType.objects.create(
            team=team,
            season='2024/2025',
            kit_type=self.home_type,
            status=TeamSeasonKitType.STATUS_APPROVED,
            source=TeamSeasonKitType.SOURCE_MODERATOR,
            approved_by=self.staff_user,
            approved_at=timezone.now(),
        )

        response = self.reject_team(team.id, user=self.moderator_user)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['detail'], 'This team has an approved Kit Museum slot.')
        self.assertEqual(response.data['usage']['approved_team_season_types'], 1)
        self.assertEqual(response.data['usage']['pending_team_season_types'], 0)

    def test_rejected_team_season_rows_do_not_block_rejection_and_are_ignored_in_list(self):
        team = Team.objects.create(name='Rejected Slot FC', is_verified=False)
        TeamSeasonKitType.objects.create(
            team=team,
            season='2024/2025',
            kit_type=self.home_type,
            status=TeamSeasonKitType.STATUS_REJECTED,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.owner,
        )

        list_response = self.list_unverified(user=self.moderator_user)
        payload = next(item for item in list_response.data['results'] if item['id'] == team.id)
        self.assertTrue(payload['can_reject'])
        self.assertEqual(payload['reject_block_reason'], '')
        self.assertEqual(payload['usage']['approved_team_season_types'], 0)
        self.assertEqual(payload['usage']['pending_team_season_types'], 0)
        self.assertEqual(payload['usage']['rejected_team_season_types'], 1)

        reject_response = self.reject_team(team.id, user=self.moderator_user)
        self.assertEqual(reject_response.status_code, 200)
        self.assertFalse(Team.objects.filter(pk=team.id).exists())

    def test_reject_deletes_stale_pending_and_rejected_team_season_rows_for_unused_team(self):
        team = Team.objects.create(name='Stale Slot FC', is_verified=False)
        TeamSeasonKitType.objects.create(
            team=team,
            season='2024/2025',
            kit_type=self.home_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.owner,
        )
        TeamSeasonKitType.objects.create(
            team=team,
            season='2023/2024',
            kit_type=self.away_type,
            status=TeamSeasonKitType.STATUS_REJECTED,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by=self.owner,
        )

        reject_response = self.reject_team(team.id, user=self.moderator_user)

        self.assertEqual(reject_response.status_code, 200)
        self.assertFalse(Team.objects.filter(pk=team.id).exists())
        action = TeamModerationAction.objects.get(pk=reject_response.data['moderation_action_id'])
        self.assertEqual(action.summary['deleted_pending_team_season_types'], 1)
        self.assertEqual(action.summary['deleted_rejected_team_season_types'], 1)

    def test_unverified_upload_with_custom_type_does_not_create_team_season_row(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            reverse('api-my-collection'),
            {
                'team_name': 'Pending Suggestion FC',
                'season': '2024/2025',
                'kit_type': 'Collector Anthem',
                'size': 'L',
                'condition': 'VERY_GOOD',
                'shirt_version_code': 'REPLICA',
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)

        team = Team.objects.get(name='Pending Suggestion FC')
        self.assertFalse(TeamSeasonKitType.objects.filter(team=team).exists())

        list_response = self.list_unverified(user=self.moderator_user)
        payload = next(item for item in list_response.data['results'] if item['id'] == team.id)
        self.assertFalse(payload['can_reject'])
        self.assertEqual(
            payload['reject_block_reason'],
            '1 upload still uses this team.',
        )
        self.assertEqual(payload['usage']['team_season_types'], 0)
        self.assertEqual(payload['usage']['approved_team_season_types'], 0)
        self.assertEqual(payload['usage']['pending_team_season_types'], 0)
        self.assertEqual(payload['usage']['rejected_team_season_types'], 0)

    def test_orphan_kit_is_cleared_during_reject_and_list_recalculation(self):
        team = Team.objects.create(name='Orphanable FC', is_verified=False)
        orphan_kit = Kit.objects.create(
            team=team,
            season='2024/2025',
            kit_type='Home',
            kit_type_ref=self.home_type,
            estimated_price=Decimal('75.00'),
        )
        userkit = UserKit.objects.create(
            user=self.owner,
            kit=orphan_kit,
            shirt_technology='REPLICA',
            shirt_version=ShirtVersion.objects.get(code='REPLICA'),
            condition='VERY_GOOD',
            size='L',
        )

        initial_list = self.list_unverified(user=self.moderator_user)
        payload = next(item for item in initial_list.data['results'] if item['id'] == team.id)
        self.assertFalse(payload['can_reject'])
        self.assertEqual(payload['usage']['userkits'], 1)
        self.assertEqual(payload['usage']['orphan_kits'], 0)

        userkit.delete()
        self.assertTrue(Kit.objects.filter(pk=orphan_kit.id).exists())

        refreshed_list = self.list_unverified(user=self.moderator_user)
        refreshed_payload = next(item for item in refreshed_list.data['results'] if item['id'] == team.id)
        self.assertTrue(refreshed_payload['can_reject'])
        self.assertEqual(refreshed_payload['reject_block_reason'], '')
        self.assertEqual(refreshed_payload['usage']['userkits'], 0)
        self.assertEqual(refreshed_payload['usage']['orphan_kits'], 1)

        reject_response = self.reject_team(team.id, user=self.moderator_user)
        self.assertEqual(reject_response.status_code, 200)
        self.assertFalse(Team.objects.filter(pk=team.id).exists())
        self.assertFalse(Kit.objects.filter(pk=orphan_kit.id).exists())


class TeamCountryBackfillMigrationTests(APITestCase):
    @staticmethod
    def run_backfill():
        migration = import_module(
            'kits.migrations.0033_country_code_country_created_at_country_created_by_and_more'
        )
        migration.backfill_team_country_from_league_country(django_apps, None)

    def test_backfill_sets_team_country_from_league_country_only_when_deterministic(self):
        england = Country.objects.create(name='England', code='EN')
        league_with_country = League.objects.create(name='Premier League', country=england)
        league_without_country = League.objects.create(name='Unknown League')

        deterministic_team = Team.objects.create(name='Deterministic FC', league=league_with_country)
        no_league_team = Team.objects.create(name='No League FC')
        no_country_league_team = Team.objects.create(name='No Country League FC', league=league_without_country)

        self.assertEqual(TeamModerationAction.objects.count(), 0)

        self.run_backfill()

        deterministic_team.refresh_from_db()
        no_league_team.refresh_from_db()
        no_country_league_team.refresh_from_db()
        self.assertEqual(deterministic_team.country_id, england.id)
        self.assertIsNone(no_league_team.country_id)
        self.assertIsNone(no_country_league_team.country_id)
        self.assertEqual(TeamModerationAction.objects.count(), 0)


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


class CollectionValueSnapshotTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="history_owner", password="password123")
        self.other_user = User.objects.create_user(username="history_other", password="password123")
        self.user.profile.is_pro = True
        self.user.profile.save()
        self.client.force_authenticate(user=self.user)
        self.team = Team.objects.create(name="History FC", is_verified=True)
        self.kit = Kit.objects.create(
            team=self.team,
            season="2024/2025",
            kit_type="Home",
            estimated_price=Decimal("100.00"),
        )

    def create_user_kit(self, **overrides):
        defaults = {
            "user": self.user,
            "kit": self.kit,
            "shirt_technology": "REPLICA",
            "condition": "VERY_GOOD",
            "size": "L",
        }
        defaults.update(overrides)
        return UserKit.objects.create(**defaults)

    def test_creating_userkit_records_kit_added_snapshot(self):
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
        snapshot = CollectionValueSnapshot.objects.get(user=self.user)
        self.assertEqual(snapshot.reason, CollectionValueSnapshot.REASON_KIT_ADDED)
        self.assertEqual(snapshot.total_value, Decimal("100.00"))
        self.assertEqual(snapshot.kits_count, 1)

    def test_updating_manual_value_records_value_snapshot(self):
        user_kit = self.create_user_kit()

        response = self.client.patch(
            reverse("api-my-collection-detail", args=[user_kit.id]),
            {"manual_value": "175.00"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        snapshot = CollectionValueSnapshot.objects.get(user=self.user)
        self.assertEqual(snapshot.reason, CollectionValueSnapshot.REASON_VALUE_UPDATED)
        self.assertEqual(snapshot.total_value, Decimal("175.00"))
        self.assertEqual(snapshot.related_userkit_id, user_kit.id)

    def test_setting_in_the_collection_false_records_lower_snapshot(self):
        user_kit = self.create_user_kit()

        response = self.client.patch(
            reverse("api-my-collection-detail", args=[user_kit.id]),
            {"in_the_collection": False},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        snapshot = CollectionValueSnapshot.objects.get(user=self.user)
        self.assertEqual(snapshot.reason, CollectionValueSnapshot.REASON_COLLECTION_STATUS_CHANGED)
        self.assertEqual(snapshot.total_value, Decimal("0.00"))
        self.assertEqual(snapshot.kits_count, 0)

    def test_restoring_in_the_collection_true_records_higher_snapshot(self):
        user_kit = self.create_user_kit(in_the_collection=False)

        response = self.client.patch(
            reverse("api-my-collection-detail", args=[user_kit.id]),
            {"in_the_collection": True},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        snapshot = CollectionValueSnapshot.objects.get(user=self.user)
        self.assertEqual(snapshot.reason, CollectionValueSnapshot.REASON_COLLECTION_STATUS_CHANGED)
        self.assertEqual(snapshot.total_value, Decimal("100.00"))
        self.assertEqual(snapshot.kits_count, 1)

    def test_deleting_userkit_records_kit_removed_snapshot(self):
        user_kit = self.create_user_kit()

        response = self.client.delete(
            reverse("api-my-collection-detail", args=[user_kit.id]),
        )

        self.assertEqual(response.status_code, 204)
        snapshot = CollectionValueSnapshot.objects.get(user=self.user)
        self.assertEqual(snapshot.reason, CollectionValueSnapshot.REASON_KIT_REMOVED)
        self.assertEqual(snapshot.total_value, Decimal("0.00"))
        self.assertEqual(snapshot.kits_count, 0)
        self.assertIsNone(snapshot.related_userkit_id)

    def test_likes_do_not_record_snapshots(self):
        user_kit = self.create_user_kit(user=self.other_user)

        response = self.client.post(reverse("toggle-like", args=[user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CollectionValueSnapshot.objects.count(), 0)

    def test_comments_do_not_record_snapshots(self):
        user_kit = self.create_user_kit(user=self.other_user)

        response = self.client.post(
            reverse("kit-comments", args=[user_kit.id]),
            {"body": "Great one"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(CollectionValueSnapshot.objects.count(), 0)

    def test_follows_do_not_record_snapshots(self):
        response = self.client.post(reverse("toggle-follow", args=[self.other_user.username]))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(CollectionValueSnapshot.objects.count(), 0)

    def test_snapshot_calculation_uses_only_active_collection_kits(self):
        self.create_user_kit()
        self.create_user_kit(manual_value=Decimal("250.00"), in_the_collection=False)

        response = self.client.get(reverse("my-collection-value-history"))

        self.assertEqual(response.status_code, 200)
        snapshot = CollectionValueSnapshot.objects.get(user=self.user)
        self.assertEqual(snapshot.reason, CollectionValueSnapshot.REASON_INITIAL)
        self.assertEqual(snapshot.total_value, Decimal("100.00"))
        self.assertEqual(snapshot.kits_count, 1)

    def test_total_value_history_matches_profile_stats_logic(self):
        self.create_user_kit(manual_value=Decimal("220.00"))

        stats_response = self.client.get(reverse("user-stats", args=[self.user.username]))
        history_response = self.client.get(reverse("my-collection-value-history"))

        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(Decimal(stats_response.data["total_value"]), Decimal("220.00"))
        self.assertEqual(Decimal(history_response.data["results"][0]["total_value"]), Decimal("220.00"))

    def test_history_endpoint_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse("my-collection-value-history"))

        self.assertEqual(response.status_code, 401)

    def test_history_endpoint_requires_pro_membership(self):
        self.user.profile.is_pro = False
        self.user.profile.save()

        response = self.client.get(reverse("my-collection-value-history"))

        self.assertEqual(response.status_code, 403)

    def test_history_endpoint_returns_only_current_user_snapshots(self):
        CollectionValueSnapshot.objects.create(
            user=self.other_user,
            total_value=Decimal("999.00"),
            kits_count=9,
            reason=CollectionValueSnapshot.REASON_INITIAL,
        )
        own_kit = self.create_user_kit(manual_value=Decimal("120.00"))
        CollectionValueSnapshot.objects.create(
            user=self.user,
            total_value=own_kit.final_value,
            kits_count=1,
            reason=CollectionValueSnapshot.REASON_KIT_ADDED,
            related_userkit=own_kit,
        )

        response = self.client.get(reverse("my-collection-value-history"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["total_value"], "120.00")

    def test_history_endpoint_creates_lazy_initial_snapshot(self):
        self.create_user_kit(manual_value=Decimal("333.00"))

        response = self.client.get(reverse("my-collection-value-history"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CollectionValueSnapshot.objects.filter(user=self.user).count(), 1)
        self.assertEqual(response.data["results"][0]["reason"], CollectionValueSnapshot.REASON_INITIAL)

    def test_history_endpoint_returns_chronological_order(self):
        first = CollectionValueSnapshot.objects.create(
            user=self.user,
            total_value=Decimal("100.00"),
            kits_count=1,
            reason=CollectionValueSnapshot.REASON_INITIAL,
        )
        second = CollectionValueSnapshot.objects.create(
            user=self.user,
            total_value=Decimal("200.00"),
            kits_count=2,
            reason=CollectionValueSnapshot.REASON_KIT_ADDED,
        )

        response = self.client.get(reverse("my-collection-value-history"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [first.id, second.id],
        )

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


class UserKitPrivateNoteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="note_owner", password="password123")
        self.other_user = User.objects.create_user(username="note_other", password="password123")
        self.team = Team.objects.create(name="Private Note FC", is_verified=True)
        self.kit = Kit.objects.create(
            team=self.team,
            season="2024/2025",
            kit_type="Home",
            estimated_price=Decimal("90.00"),
        )
        self.user_kit = UserKit.objects.create(
            user=self.owner,
            kit=self.kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
            private_note="Collector-only details",
        )

    def test_create_userkit_saves_private_note(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            reverse("api-my-collection"),
            {
                "team_name": self.team.name,
                "season": "2025/2026",
                "kit_type": "Away",
                "size": "L",
                "condition": "VERY_GOOD",
                "shirt_technology": "REPLICA",
                "private_note": "  Bought from a local seller  ",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        created = UserKit.objects.get(pk=response.data["id"])
        self.assertEqual(created.private_note, "Bought from a local seller")
        self.assertEqual(response.data["private_note"], "Bought from a local seller")
        self.assertTrue(response.data["has_private_note"])

    def test_update_userkit_updates_private_note(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("api-my-collection-detail", args=[self.user_kit.id]),
            {"private_note": "  Updated note  "},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.user_kit.refresh_from_db()
        self.assertEqual(self.user_kit.private_note, "Updated note")
        self.assertEqual(response.data["private_note"], "Updated note")
        self.assertTrue(response.data["has_private_note"])

    def test_owner_can_see_private_note_in_own_collection_response(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(reverse("api-user-collection", args=[self.owner.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["private_note"], "Collector-only details")
        self.assertTrue(response.data[0]["has_private_note"])

    def test_owner_can_see_private_note_in_direct_kit_response(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(reverse("kit-detail", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["private_note"], "Collector-only details")
        self.assertTrue(response.data["has_private_note"])

    def test_non_owner_cannot_see_private_note_in_public_profile_response(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(reverse("api-user-collection", args=[self.owner.username]))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("private_note", response.data[0])
        self.assertNotIn("has_private_note", response.data[0])

    def test_non_owner_cannot_see_private_note_in_direct_kit_response(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(reverse("kit-detail", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("private_note", response.data)
        self.assertNotIn("has_private_note", response.data)

    def test_anonymous_user_cannot_see_private_note(self):
        response = self.client.get(reverse("kit-detail", args=[self.user_kit.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("private_note", response.data)
        self.assertNotIn("has_private_note", response.data)

    def test_explore_response_does_not_leak_private_note(self):
        response = self.client.get(reverse("explore-kits"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("private_note", response.data[0])
        self.assertNotIn("has_private_note", response.data[0])

    def test_feed_response_does_not_leak_private_note(self):
        Follow.objects.create(follower=self.other_user, following=self.owner)
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(reverse("following-feed"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertNotIn("private_note", response.data["results"][0])
        self.assertNotIn("has_private_note", response.data["results"][0])

    def test_private_note_update_does_not_create_collection_value_snapshot(self):
        self.owner.profile.is_pro = True
        self.owner.profile.save()
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("api-my-collection-detail", args=[self.user_kit.id]),
            {"private_note": "Fresh note only"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CollectionValueSnapshot.objects.count(), 0)

    def test_private_note_max_length_validation(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("api-my-collection-detail", args=[self.user_kit.id]),
            {"private_note": "a" * 2001},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("private_note", response.data)


class WishlistItemAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="wishlist_owner", password="password123")
        self.other_user = User.objects.create_user(username="wishlist_other", password="password123")
        self.team = Team.objects.create(name="Arsenal F.C.", is_verified=True)
        self.goalkeeper_team = Team.objects.create(name="Chelsea F.C.", is_verified=True)
        self.special_team = Team.objects.create(name="Barcelona", is_verified=True)

    def create_user_kit(self, *, team, season, kit_type, owner=None, image_name=None):
        owner = owner or self.other_user
        kit = Kit.objects.create(team=team, season=season, kit_type=kit_type, estimated_price=Decimal("50.00"))
        user_kit = UserKit.objects.create(
            user=owner,
            kit=kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )
        if image_name:
            UserKitImage.objects.create(
                user_kit=user_kit,
                image=SimpleUploadedFile(image_name, b"fake-image-bytes", content_type="image/jpeg"),
            )
        return user_kit

    def create_wishlist_item(self, **overrides):
        defaults = {
            "user": self.user,
            "team": self.team,
            "season": "2018/2019",
            "kit_type": "Away",
        }
        defaults.update(overrides)
        return WishlistItem.objects.create(**defaults)

    def toggle_payload(self, **overrides):
        payload = {
            "team_id": self.team.id,
            "season": "2018/2019",
            "kit_type": "Away",
        }
        payload.update(overrides)
        return payload

    def test_authenticated_user_can_add_wishlist_item(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse("wishlist-toggle"), self.toggle_payload(), format="json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_wishlisted"])
        self.assertEqual(WishlistItem.objects.count(), 1)
        self.assertEqual(response.data["item"]["team_name"], self.team.name)
        self.assertEqual(response.data["item"]["kit_type"], "Away")

    def test_unauthenticated_user_cannot_add_wishlist_item(self):
        response = self.client.post(reverse("wishlist-toggle"), self.toggle_payload(), format="json")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_duplicate_variant_is_blocked_by_unique_constraint(self):
        self.create_wishlist_item()

        with self.assertRaises(IntegrityError):
            WishlistItem.objects.create(
                user=self.user,
                team=self.team,
                season="2018/2019",
                kit_type="Away",
            )

    def test_toggle_existing_item_removes_it(self):
        self.client.force_authenticate(user=self.user)
        self.create_wishlist_item()

        response = self.client.post(reverse("wishlist-toggle"), self.toggle_payload(), format="json")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_wishlisted"])
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_free_user_limit_is_enforced_at_ten_items(self):
        self.client.force_authenticate(user=self.user)

        for index in range(10):
            team = Team.objects.create(name=f"Free Limit FC {index}", is_verified=True)
            WishlistItem.objects.create(
                user=self.user,
                team=team,
                season="2018/2019",
                kit_type="Away",
            )

        response = self.client.post(reverse("wishlist-toggle"), self.toggle_payload(), format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "wishlist_limit_reached")
        self.assertEqual(response.data["limit"], 10)
        self.assertEqual(WishlistItem.objects.filter(user=self.user).count(), 10)

    def test_pro_user_can_exceed_free_limit(self):
        self.user.profile.is_pro = True
        self.user.profile.save()
        self.client.force_authenticate(user=self.user)

        for index in range(10):
            team = Team.objects.create(name=f"Pro Limit FC {index}", is_verified=True)
            WishlistItem.objects.create(
                user=self.user,
                team=team,
                season="2018/2019",
                kit_type="Away",
            )

        response = self.client.post(reverse("wishlist-toggle"), self.toggle_payload(), format="json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_wishlisted"])
        self.assertEqual(WishlistItem.objects.filter(user=self.user).count(), 11)

    def test_existing_item_toggle_off_works_even_at_free_limit(self):
        self.client.force_authenticate(user=self.user)
        existing_item = self.create_wishlist_item()

        for index in range(9):
            team = Team.objects.create(name=f"Limit Toggle FC {index}", is_verified=True)
            WishlistItem.objects.create(
                user=self.user,
                team=team,
                season="2018/2019",
                kit_type="Away",
            )

        response = self.client.post(reverse("wishlist-toggle"), self.toggle_payload(), format="json")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_wishlisted"])
        self.assertFalse(WishlistItem.objects.filter(pk=existing_item.id).exists())

    def test_owner_can_delete_own_wishlist_item(self):
        self.client.force_authenticate(user=self.user)
        item = self.create_wishlist_item()

        response = self.client.delete(reverse("wishlist-detail", args=[item.id]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(WishlistItem.objects.filter(pk=item.id).exists())

    def test_user_cannot_delete_other_users_wishlist_item(self):
        self.client.force_authenticate(user=self.other_user)
        item = WishlistItem.objects.create(
            user=self.user,
            team=self.team,
            season="2018/2019",
            kit_type="Away",
        )

        response = self.client.delete(reverse("wishlist-detail", args=[item.id]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(WishlistItem.objects.filter(pk=item.id).exists())

    def test_my_wishlist_endpoint_returns_only_current_user_items(self):
        self.client.force_authenticate(user=self.user)
        own_item = self.create_wishlist_item()
        WishlistItem.objects.create(
            user=self.other_user,
            team=self.goalkeeper_team,
            season="2019/2020",
            kit_type="Goalkeeper",
        )

        response = self.client.get(reverse("my-wishlist"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], own_item.id)
        self.assertEqual(response.data[0]["owner_username"], self.user.username)

    def test_public_user_wishlist_endpoint_returns_items(self):
        item = self.create_wishlist_item()

        response = self.client.get(reverse("user-wishlist", args=[self.user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], item.id)
        self.assertEqual(response.data[0]["owner_username"], self.user.username)
        self.assertNotIn("user", response.data[0])

    def test_serializer_includes_preview_image_when_matching_upload_exists(self):
        self.create_user_kit(
            team=self.team,
            season="2018/2019",
            kit_type="Away",
            image_name="away-preview.jpg",
        )
        self.create_wishlist_item()

        response = self.client.get(reverse("user-wishlist", args=[self.user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data[0]["has_uploads"])
        self.assertIn("/media/user_kits/", response.data[0]["preview_image"])

    def test_preview_prefers_most_liked_matching_upload(self):
        less_liked = self.create_user_kit(
            team=self.team,
            season="2018/2019",
            kit_type="Away",
            image_name="less-liked.jpg",
        )
        most_liked = self.create_user_kit(
            team=self.team,
            season="2018/2019",
            kit_type="Away",
            image_name="most-liked.jpg",
        )
        fan_one = User.objects.create_user(username="fan_one", password="password123")
        fan_two = User.objects.create_user(username="fan_two", password="password123")
        less_liked.likes.add(fan_one)
        most_liked.likes.add(fan_one, fan_two)
        self.create_wishlist_item()

        response = self.client.get(reverse("user-wishlist", args=[self.user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("most-liked", response.data[0]["preview_image"])

    def test_goalkeeper_compatibility_matches_stored_gk_upload(self):
        self.create_user_kit(
            team=self.goalkeeper_team,
            season="2020/2021",
            kit_type="GK",
            image_name="goalkeeper-preview.jpg",
        )
        WishlistItem.objects.create(
            user=self.user,
            team=self.goalkeeper_team,
            season="2020/2021",
            kit_type="Goalkeeper",
        )

        response = self.client.get(reverse("user-wishlist", args=[self.user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["kit_type"], "Goalkeeper")
        self.assertTrue(response.data[0]["has_uploads"])
        self.assertIn("goalkeeper-preview", response.data[0]["preview_image"])

    def test_special_compatibility_matches_special_edition_upload(self):
        self.create_user_kit(
            team=self.special_team,
            season="2021/2022",
            kit_type="Special Edition",
            image_name="special-preview.jpg",
        )
        WishlistItem.objects.create(
            user=self.user,
            team=self.special_team,
            season="2021/2022",
            kit_type="Special",
        )

        response = self.client.get(reverse("user-wishlist", args=[self.user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["kit_type"], "Special")
        self.assertTrue(response.data[0]["has_uploads"])
        self.assertIn("special-preview", response.data[0]["preview_image"])

    def test_wishlist_url_is_generated_and_encoded(self):
        item = self.create_wishlist_item(season="2018/2019", kit_type="Away")

        response = self.client.get(reverse("user-wishlist", args=[self.user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], item.id)
        self.assertEqual(
            response.data[0]["url"],
            f"/history/team/arsenal-fc/variants?{urlencode({'season': '2018/2019', 'type': 'Away'})}",
        )


class TopKitsByTeamAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="museum_owner", password="password123")
        self.team = Team.objects.create(name="Museum FC", is_verified=True)

    def create_user_kit(self, season, kit_type, added_at):
        kit = Kit.objects.create(
            team=self.team,
            season=season,
            kit_type=kit_type,
            estimated_price=Decimal("50.00"),
        )
        user_kit = UserKit.objects.create(
            user=self.owner,
            kit=kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
        )
        UserKit.objects.filter(id=user_kit.id).update(added_at=added_at)
        return user_kit

    def test_top_kits_by_team_endpoint_returns_full_team_dataset_without_pagination(self):
        for index in range(13):
            self.create_user_kit(
                season=f"20{10 + index}/20{11 + index}",
                kit_type="Home",
                added_at=timezone.now() - timedelta(hours=index),
            )

        response = self.client.get(reverse("top-kits-by-team", args=[self.team.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 13)


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


class FollowingFeedAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("following-feed")

        self.viewer = User.objects.create_user(username="viewer", password="password123")
        self.followed_one = User.objects.create_user(username="followed1", password="password123")
        self.followed_two = User.objects.create_user(username="followed2", password="password123")
        self.other_user = User.objects.create_user(username="otheruser", password="password123")

        self.team = Team.objects.create(name="Feed FC", is_verified=True)

        Follow.objects.create(follower=self.viewer, following=self.followed_one)
        Follow.objects.create(follower=self.viewer, following=self.followed_two)

        self.viewer_kit = self.create_user_kit(
            self.viewer,
            "2024/2025",
            "Home",
            timezone.now() - timedelta(hours=4),
            image_name="viewer.jpg",
        )
        self.non_followed_kit = self.create_user_kit(
            self.other_user,
            "2024/2025",
            "Away",
            timezone.now() - timedelta(hours=3),
            image_name="other.jpg",
        )
        self.oldest_followed_kit = self.create_user_kit(
            self.followed_one,
            "2022/2023",
            "Third",
            timezone.now() - timedelta(hours=2),
            image_name="oldest.jpg",
        )
        self.middle_followed_kit = self.create_user_kit(
            self.followed_two,
            "2023/2024",
            "Away",
            timezone.now() - timedelta(hours=1),
            image_name="middle.jpg",
        )
        self.newest_followed_kit = self.create_user_kit(
            self.followed_one,
            "2025/2026",
            "Home",
            timezone.now(),
            image_name="newest.jpg",
        )

    def create_user_kit(self, user, season, kit_type, added_at, image_name=None):
        kit = Kit.objects.create(
            team=self.team,
            season=season,
            kit_type=kit_type,
            estimated_price=Decimal("100.00"),
        )
        user_kit = UserKit.objects.create(
            user=user,
            kit=kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
            in_the_collection=True,
        )
        UserKit.objects.filter(pk=user_kit.pk).update(added_at=added_at)
        user_kit.refresh_from_db()

        if image_name:
            UserKitImage.objects.create(
                user_kit=user_kit,
                image=SimpleUploadedFile(image_name, b"feed-bytes", content_type="image/jpeg"),
                order=0,
            )

        return user_kit

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_authenticated_user_sees_only_followed_users_kits(self):
        self.client.force_authenticate(user=self.viewer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [
                self.newest_followed_kit.id,
                self.middle_followed_kit.id,
                self.oldest_followed_kit.id,
            ],
        )

    def test_non_followed_users_and_own_kits_are_excluded(self):
        self.client.force_authenticate(user=self.viewer)

        response = self.client.get(self.url)
        returned_ids = [item["id"] for item in response.data["results"]]

        self.assertNotIn(self.non_followed_kit.id, returned_ids)
        self.assertNotIn(self.viewer_kit.id, returned_ids)

    def test_response_includes_owner_and_kit_fields_needed_by_frontend(self):
        self.client.force_authenticate(user=self.viewer)

        response = self.client.get(self.url, {"limit": 1})

        self.assertEqual(response.status_code, 200)
        item = response.data["results"][0]
        self.assertEqual(item["owner_id"], self.followed_one.id)
        self.assertEqual(item["owner_username"], self.followed_one.username)
        self.assertIn("owner_avatar", item)
        self.assertEqual(item["kit"]["team"]["name"], "Feed FC")
        self.assertEqual(item["kit"]["season"], "2025/2026")
        self.assertEqual(item["kit"]["kit_type"], "Home")
        self.assertEqual(len(item["images"]), 1)

    def test_limit_works_and_has_more_is_true_when_older_items_exist(self):
        self.client.force_authenticate(user=self.viewer)

        response = self.client.get(self.url, {"limit": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertTrue(response.data["has_more"])

    def test_before_returns_older_items(self):
        self.client.force_authenticate(user=self.viewer)

        first_page = self.client.get(self.url, {"limit": 2})
        before_id = first_page.data["results"][-1]["id"]

        second_page = self.client.get(self.url, {"limit": 2, "before": before_id})

        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(
            [item["id"] for item in second_page.data["results"]],
            [self.oldest_followed_kit.id],
        )
        self.assertFalse(second_page.data["has_more"])

    def test_invalid_before_is_handled_safely(self):
        self.client.force_authenticate(user=self.viewer)

        invalid_response = self.client.get(self.url, {"before": "bad-id"})
        missing_response = self.client.get(self.url, {"before": 999999})

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.data["before"], ["before must be a valid kit id."])
        self.assertEqual(missing_response.status_code, 400)
        self.assertEqual(missing_response.data["before"], ["Kit not found in feed."])


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="owner", password="password123")
        self.actor = User.objects.create_user(username="actor", password="password123")
        self.other_user = User.objects.create_user(username="other", password="password123")

        self.team = Team.objects.create(name="Notify FC", is_verified=True)
        self.kit = Kit.objects.create(
            team=self.team,
            season="2024/2025",
            kit_type="Home",
            estimated_price=Decimal("100.00"),
        )
        self.user_kit = UserKit.objects.create(
            user=self.owner,
            kit=self.kit,
            shirt_technology="REPLICA",
            condition="VERY_GOOD",
            size="L",
            in_the_collection=True,
        )
        UserKitImage.objects.create(
            user_kit=self.user_kit,
            image=SimpleUploadedFile("notification-preview.jpg", b"preview", content_type="image/jpeg"),
            order=0,
        )

        self.like_url = reverse("toggle-like", args=[self.user_kit.id])
        self.follow_url = reverse("toggle-follow", args=[self.owner.username])
        self.comment_url = reverse("kit-comments", args=[self.user_kit.id])
        self.list_url = reverse("notification-list")
        self.unread_count_url = reverse("notification-unread-count")
        self.mark_read_url = reverse("notification-mark-read")

    def test_liking_someone_elses_kit_creates_notification_for_owner(self):
        self.client.force_authenticate(user=self.actor)

        response = self.client.post(self.like_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="kit_like",
                kit=self.user_kit,
            ).exists()
        )

    def test_liking_own_kit_does_not_create_notification(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(self.like_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Notification.objects.exists())

    def test_unlike_removes_matching_kit_like_notification(self):
        self.client.force_authenticate(user=self.actor)

        self.client.post(self.like_url)
        response = self.client.post(self.like_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="kit_like",
                kit=self.user_kit,
            ).exists()
        )

    def test_repeated_like_unlike_relike_does_not_accumulate_duplicates(self):
        self.client.force_authenticate(user=self.actor)

        self.client.post(self.like_url)
        self.client.post(self.like_url)
        self.client.post(self.like_url)

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="kit_like",
                kit=self.user_kit,
            ).count(),
            1,
        )

    def test_following_a_user_creates_notification_for_followed_user(self):
        self.client.force_authenticate(user=self.actor)

        response = self.client.post(self.follow_url)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="follow",
                kit__isnull=True,
            ).exists()
        )

    def test_commenting_on_someone_elses_kit_creates_notification_for_kit_owner(self):
        self.client.force_authenticate(user=self.actor)

        response = self.client.post(
            self.comment_url,
            {"body": "Great shirt"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        created_comment = KitComment.objects.get(pk=response.data["id"])
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="kit_comment",
                kit=self.user_kit,
                comment=created_comment,
            ).exists()
        )

    def test_commenting_on_own_kit_does_not_notify(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.comment_url,
            {"body": "My own note"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(Notification.objects.exists())

    def test_kit_comment_notification_payload_includes_actor_kit_and_comment_preview(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.actor,
            body="This is a very good kit and the details look excellent.",
        )
        Notification.objects.create(
            recipient=self.owner,
            actor=self.actor,
            type="kit_comment",
            kit=self.user_kit,
            comment=comment,
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        payload = response.data["results"][0]
        self.assertEqual(payload["actor"]["username"], self.actor.username)
        self.assertEqual(payload["kit"]["id"], self.user_kit.id)
        self.assertEqual(payload["comment"]["id"], comment.id)
        self.assertEqual(payload["comment"]["author_username"], self.actor.username)
        self.assertEqual(payload["comment"]["body_preview"], comment.body)

    def test_replying_to_someone_elses_comment_creates_notification_for_target_author(self):
        parent = KitComment.objects.create(
            kit=self.user_kit,
            user=self.owner,
            body="Original comment",
        )
        self.client.force_authenticate(user=self.actor)

        response = self.client.post(
            reverse("comment-reply", args=[parent.id]),
            {"body": "Replying here"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        created_reply = KitComment.objects.get(pk=response.data["id"])
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="comment_reply",
                kit=self.user_kit,
                comment=created_reply,
            ).exists()
        )

    def test_replying_to_own_comment_does_not_notify(self):
        parent = KitComment.objects.create(
            kit=self.user_kit,
            user=self.actor,
            body="My own comment",
        )
        self.client.force_authenticate(user=self.actor)

        response = self.client.post(
            reverse("comment-reply", args=[parent.id]),
            {"body": "Self reply"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(Notification.objects.exists())

    def test_replying_to_a_reply_notifies_clicked_reply_author(self):
        parent = KitComment.objects.create(
            kit=self.user_kit,
            user=self.owner,
            body="Top level",
        )
        first_reply = KitComment.objects.create(
            kit=self.user_kit,
            user=self.other_user,
            body="First reply",
            parent=parent,
            reply_to=parent,
        )
        self.client.force_authenticate(user=self.actor)

        response = self.client.post(
            reverse("comment-reply", args=[first_reply.id]),
            {"body": "Reply to reply"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        created_reply = KitComment.objects.get(pk=response.data["id"])
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.other_user,
                actor=self.actor,
                type="comment_reply",
                kit=self.user_kit,
                comment=created_reply,
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="comment_reply",
                comment=created_reply,
            ).exists()
        )

    def test_comment_reply_notification_payload_includes_kit_and_comment_info(self):
        reply = KitComment.objects.create(
            kit=self.user_kit,
            user=self.actor,
            body="Reply body preview text",
        )
        Notification.objects.create(
            recipient=self.owner,
            actor=self.actor,
            type="comment_reply",
            kit=self.user_kit,
            comment=reply,
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        payload = response.data["results"][0]
        self.assertEqual(payload["type"], "comment_reply")
        self.assertEqual(payload["kit"]["owner_username"], self.owner.username)
        self.assertEqual(payload["comment"]["id"], reply.id)
        self.assertEqual(payload["comment"]["body_preview"], "Reply body preview text")

    def test_liking_someone_elses_comment_creates_notification_for_comment_author(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.owner,
            body="Like this comment",
        )
        self.client.force_authenticate(user=self.actor)

        response = self.client.post(reverse("comment-like", args=[comment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="comment_like",
                kit=self.user_kit,
                comment=comment,
            ).exists()
        )

    def test_liking_own_comment_does_not_notify(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.actor,
            body="My own comment",
        )
        self.client.force_authenticate(user=self.actor)

        response = self.client.post(reverse("comment-like", args=[comment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Notification.objects.exists())

    def test_unliking_comment_deletes_matching_comment_like_notification(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.owner,
            body="Unlike this comment",
        )
        self.client.force_authenticate(user=self.actor)

        self.client.post(reverse("comment-like", args=[comment.id]))
        response = self.client.post(reverse("comment-like", args=[comment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="comment_like",
                kit=self.user_kit,
                comment=comment,
            ).exists()
        )

    def test_repeated_comment_like_unlike_relike_does_not_accumulate_duplicates(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.owner,
            body="Duplicate protection",
        )
        self.client.force_authenticate(user=self.actor)

        self.client.post(reverse("comment-like", args=[comment.id]))
        self.client.post(reverse("comment-like", args=[comment.id]))
        self.client.post(reverse("comment-like", args=[comment.id]))

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="comment_like",
                kit=self.user_kit,
                comment=comment,
            ).count(),
            1,
        )

    def test_unfollowing_does_not_create_new_notification(self):
        self.client.force_authenticate(user=self.actor)

        self.client.post(self.follow_url)
        self.client.post(self.follow_url)

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="follow",
                kit__isnull=True,
            ).count(),
            1,
        )

    def test_refollow_does_not_duplicate_follow_notification(self):
        self.client.force_authenticate(user=self.actor)

        self.client.post(self.follow_url)
        self.client.post(self.follow_url)
        self.client.post(self.follow_url)

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.owner,
                actor=self.actor,
                type="follow",
                kit__isnull=True,
            ).count(),
            1,
        )

    def test_notifications_list_returns_only_current_users_notifications(self):
        own_notification = Notification.objects.create(
            recipient=self.owner,
            actor=self.actor,
            type="follow",
        )
        Notification.objects.create(
            recipient=self.other_user,
            actor=self.actor,
            type="follow",
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["results"]], [own_notification.id])

    def test_unread_count_returns_correct_count(self):
        Notification.objects.create(recipient=self.owner, actor=self.actor, type="follow")
        Notification.objects.create(recipient=self.owner, actor=self.other_user, type="follow")
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.unread_count_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 2)

    def test_unread_count_includes_new_notification_types(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.actor,
            body="Count me",
        )
        Notification.objects.create(recipient=self.owner, actor=self.actor, type="kit_comment", kit=self.user_kit, comment=comment)
        Notification.objects.create(recipient=self.owner, actor=self.other_user, type="comment_like", kit=self.user_kit, comment=comment)
        Notification.objects.create(recipient=self.owner, actor=User.objects.create_user(username="replyer", password="password123"), type="comment_reply", kit=self.user_kit, comment=comment)
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.unread_count_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 3)

    def test_mark_read_sets_read_at(self):
        first = Notification.objects.create(recipient=self.owner, actor=self.actor, type="follow")
        second = Notification.objects.create(recipient=self.owner, actor=self.other_user, type="follow")
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(self.mark_read_url, {}, format="json")

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 0)
        self.assertIsNotNone(first.read_at)
        self.assertIsNotNone(second.read_at)

    def test_mark_read_marks_all_notification_types_as_read(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.actor,
            body="Mark all types",
        )
        notifications = [
            Notification.objects.create(recipient=self.owner, actor=self.actor, type="kit_like", kit=self.user_kit),
            Notification.objects.create(recipient=self.owner, actor=self.other_user, type="follow"),
            Notification.objects.create(recipient=self.owner, actor=self.actor, type="kit_comment", kit=self.user_kit, comment=comment),
            Notification.objects.create(recipient=self.owner, actor=self.other_user, type="comment_like", kit=self.user_kit, comment=comment),
            Notification.objects.create(recipient=self.owner, actor=User.objects.create_user(username="reply-mark", password="password123"), type="comment_reply", kit=self.user_kit, comment=comment),
        ]
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(self.mark_read_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        for notification in notifications:
            notification.refresh_from_db()
            self.assertIsNotNone(notification.read_at)

    def test_unauthenticated_users_cannot_access_notification_endpoints(self):
        list_response = self.client.get(self.list_url)
        count_response = self.client.get(self.unread_count_url)
        mark_response = self.client.post(self.mark_read_url, {}, format="json")

        self.assertEqual(list_response.status_code, 401)
        self.assertEqual(count_response.status_code, 401)
        self.assertEqual(mark_response.status_code, 401)

    def test_notification_payload_includes_actor_public_info_only(self):
        notification = Notification.objects.create(
            recipient=self.owner,
            actor=self.actor,
            type="follow",
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        actor_payload = response.data["results"][0]["actor"]
        self.assertEqual(response.data["results"][0]["id"], notification.id)
        self.assertEqual(actor_payload["username"], self.actor.username)
        self.assertIn("avatar", actor_payload)
        self.assertNotIn("email", actor_payload)
        self.assertIsNone(response.data["results"][0]["comment"])

    def test_kit_like_notification_payload_includes_kit_info(self):
        Notification.objects.create(
            recipient=self.owner,
            actor=self.actor,
            type="kit_like",
            kit=self.user_kit,
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        kit_payload = response.data["results"][0]["kit"]
        self.assertEqual(kit_payload["id"], self.user_kit.id)
        self.assertEqual(kit_payload["owner_username"], self.owner.username)
        self.assertEqual(kit_payload["team_name"], "Notify FC")
        self.assertEqual(kit_payload["season"], "2024/2025")
        self.assertEqual(kit_payload["kit_type"], "Home")
        self.assertIsNone(response.data["results"][0]["comment"])

    def test_kit_like_notification_payload_includes_preview_image_if_available(self):
        Notification.objects.create(
            recipient=self.owner,
            actor=self.actor,
            type="kit_like",
            kit=self.user_kit,
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("/media/user_kits/notification-preview", response.data["results"][0]["kit"]["preview_image"])

    def test_list_endpoint_returns_new_types_correctly(self):
        comment = KitComment.objects.create(
            kit=self.user_kit,
            user=self.actor,
            body="This preview text should appear in the payload for list endpoint coverage.",
        )
        Notification.objects.create(recipient=self.owner, actor=self.actor, type="kit_comment", kit=self.user_kit, comment=comment)
        Notification.objects.create(recipient=self.owner, actor=self.other_user, type="comment_like", kit=self.user_kit, comment=comment)
        Notification.objects.create(recipient=self.owner, actor=User.objects.create_user(username="reply-list", password="password123"), type="comment_reply", kit=self.user_kit, comment=comment)
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        returned_types = {item["type"] for item in response.data["results"]}
        self.assertTrue({"kit_comment", "comment_like", "comment_reply"}.issubset(returned_types))

    def test_notification_list_pagination_with_limit_and_before_works(self):
        oldest = Notification.objects.create(recipient=self.owner, actor=self.actor, type="follow")
        middle = Notification.objects.create(recipient=self.owner, actor=self.other_user, type="follow")
        newest_actor = User.objects.create_user(username="latest", password="password123")
        newest = Notification.objects.create(recipient=self.owner, actor=newest_actor, type="follow")
        self.client.force_authenticate(user=self.owner)

        first_page = self.client.get(self.list_url, {"limit": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual([item["id"] for item in first_page.data["results"]], [newest.id, middle.id])
        self.assertTrue(first_page.data["has_more"])

        second_page = self.client.get(self.list_url, {"limit": 2, "before": middle.id})

        self.assertEqual(second_page.status_code, 200)
        self.assertEqual([item["id"] for item in second_page.data["results"]], [oldest.id])
        self.assertFalse(second_page.data["has_more"])

    def test_invalid_notification_before_is_rejected(self):
        self.client.force_authenticate(user=self.owner)

        invalid_response = self.client.get(self.list_url, {"before": "bad-id"})
        missing_response = self.client.get(self.list_url, {"before": 999999})

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.data["before"], ["before must be a valid notification id."])
        self.assertEqual(missing_response.status_code, 400)
        self.assertEqual(missing_response.data["before"], ["Notification not found."])
