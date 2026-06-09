from dataclasses import dataclass
import re

from django.db import transaction
from django.db.models import Count
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from .models import (
    Kit,
    Profile,
    Team,
    TeamModerationAction,
    TeamSeasonKitType,
    UserKit,
    WishlistItem,
    build_team_slug,
    normalize_wishlist_kit_type,
)


TEAM_MERGE_UNDO_BLOCK_REASON = 'Team merge undo requires manual review.'
TEAM_REJECT_UNDO_BLOCK_REASON = 'Deleted teams cannot be restored automatically.'

_PUNCTUATION_PATTERN = re.compile(r'[^a-z0-9\s]+')
_WHITESPACE_PATTERN = re.compile(r'\s+')


class TeamModerationConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'This team moderation action can no longer be completed.'
    default_code = 'team_moderation_conflict'

    def __init__(self, detail=None, code=None):
        self.raw_detail = detail if detail is not None else self.default_detail
        super().__init__(detail=detail, code=code)


@dataclass
class TeamUsage:
    kits: int
    userkits: int
    wishlist_items: int
    favorite_profiles: int
    team_season_types: int

    def as_dict(self):
        return {
            'kits': self.kits,
            'userkits': self.userkits,
            'wishlist_items': self.wishlist_items,
            'favorite_profiles': self.favorite_profiles,
            'team_season_types': self.team_season_types,
        }

    def is_unused(self):
        return not any(self.as_dict().values())


def normalize_team_name_for_matching(name):
    lowered = (name or '').strip().lower()
    lowered = _PUNCTUATION_PATTERN.sub(' ', lowered)
    return _WHITESPACE_PATTERN.sub(' ', lowered).strip()


def team_name_tokens(name):
    return {
        token
        for token in normalize_team_name_for_matching(name).split()
        if len(token) >= 3
    }


def get_team_usage(team):
    usage = Team.objects.filter(pk=team.pk).annotate(
        kits_count=Count('kits', distinct=True),
        userkits_count=Count('kits__owned_by', distinct=True),
        wishlist_count=Count('wishlist_items', distinct=True),
        favorite_team_count=Count('fans', distinct=True),
        team_season_count=Count('season_kit_types', distinct=True),
    ).values(
        'kits_count',
        'userkits_count',
        'wishlist_count',
        'favorite_team_count',
        'team_season_count',
    ).first()

    if usage is None:
        return TeamUsage(0, 0, 0, 0, 0)

    return TeamUsage(
        kits=usage['kits_count'] or 0,
        userkits=usage['userkits_count'] or 0,
        wishlist_items=usage['wishlist_count'] or 0,
        favorite_profiles=usage['favorite_team_count'] or 0,
        team_season_types=usage['team_season_count'] or 0,
    )


def snapshot_team(team):
    if team is None:
        return None

    return {
        'id': team.id,
        'name': team.name,
        'slug': build_team_slug(team.name),
        'is_verified': team.is_verified,
        'league_id': team.league_id,
        'logo': team.logo.name if team.logo else None,
    }


def build_team_moderation_action(
    *,
    actor,
    action_type,
    source_team,
    target_team=None,
    previous_state=None,
    resulting_state=None,
    summary=None,
    is_reversible=False,
    undo_block_reason='',
):
    return TeamModerationAction.objects.create(
        actor=actor,
        action_type=action_type,
        source_team_id_snapshot=source_team.id if source_team is not None else None,
        source_team_name=source_team.name if source_team is not None else '',
        target_team=target_team,
        target_team_name=target_team.name if target_team is not None else '',
        previous_state=previous_state or {},
        resulting_state=resulting_state or {},
        summary=summary or {},
        is_reversible=is_reversible,
        undo_block_reason=undo_block_reason,
    )


def canonical_legacy_kit_type(kit_type):
    return normalize_wishlist_kit_type(kit_type or '')


def get_kit_duplicate_key(kit):
    if kit.kit_type_ref_id is not None:
        return (
            kit.season,
            'kit_type_ref',
            kit.kit_type_ref_id,
        )

    return (
        kit.season,
        'legacy_kit_type',
        canonical_legacy_kit_type(kit.kit_type),
    )


def merge_kit_metadata(source_kit, target_kit):
    update_fields = []

    if target_kit.kit_type_ref_id is None and source_kit.kit_type_ref_id is not None:
        target_kit.kit_type_ref = source_kit.kit_type_ref
        target_kit.kit_type = source_kit.kit_type_ref.name
        update_fields.extend(['kit_type_ref', 'kit_type'])

    if target_kit.estimated_price == 0 and source_kit.estimated_price != 0:
        target_kit.estimated_price = source_kit.estimated_price
        update_fields.append('estimated_price')

    if not target_kit.main_image and source_kit.main_image:
        target_kit.main_image = source_kit.main_image
        update_fields.append('main_image')

    if update_fields:
        target_kit.save(update_fields=update_fields)


def reconcile_wishlist_items(source_team, target_team):
    moved_wishlist_items = 0
    deduplicated_wishlist_items = 0

    target_items = list(
        WishlistItem.objects.select_for_update().filter(team=target_team).order_by('id')
    )
    target_lookup = {
        (item.user_id, item.season, item.kit_type): item
        for item in target_items
    }

    source_items = list(
        WishlistItem.objects.select_for_update().filter(team=source_team).order_by('id')
    )
    for item in source_items:
        key = (item.user_id, item.season, item.kit_type)
        duplicate = target_lookup.get(key)

        if duplicate is None:
            item.team = target_team
            item.save(update_fields=['team'])
            target_lookup[key] = item
            moved_wishlist_items += 1
            continue

        duplicate_update_fields = []
        if duplicate.kit_type_ref_id is None and item.kit_type_ref_id is not None:
            duplicate.kit_type_ref = item.kit_type_ref
            duplicate_update_fields.append('kit_type_ref')
        if duplicate.source_userkit_id is None and item.source_userkit_id is not None:
            duplicate.source_userkit = item.source_userkit
            duplicate_update_fields.append('source_userkit')
        if duplicate_update_fields:
            duplicate.save(update_fields=duplicate_update_fields)

        item.delete()
        deduplicated_wishlist_items += 1

    return moved_wishlist_items, deduplicated_wishlist_items


def reconcile_team_season_rows(source_team, target_team):
    moved_team_season_types = 0
    reconciled_team_season_types = 0

    target_rows = list(
        TeamSeasonKitType.objects.select_for_update().filter(team=target_team).order_by('id')
    )
    target_lookup = {
        (row.season, row.kit_type_id): row
        for row in target_rows
    }

    source_rows = list(
        TeamSeasonKitType.objects.select_for_update().filter(team=source_team).order_by('id')
    )
    source_priority = {
        TeamSeasonKitType.SOURCE_SYSTEM_DEFAULT: 3,
        TeamSeasonKitType.SOURCE_MODERATOR: 2,
        TeamSeasonKitType.SOURCE_UPLOAD: 1,
    }

    for row in source_rows:
        key = (row.season, row.kit_type_id)
        duplicate = target_lookup.get(key)

        if duplicate is None:
            row.team = target_team
            row.save(update_fields=['team'])
            target_lookup[key] = row
            moved_team_season_types += 1
            continue

        update_fields = []
        if row.status == TeamSeasonKitType.STATUS_APPROVED and duplicate.status != TeamSeasonKitType.STATUS_APPROVED:
            duplicate.status = TeamSeasonKitType.STATUS_APPROVED
            duplicate.approved_by = row.approved_by
            duplicate.approved_at = row.approved_at
            update_fields.extend(['status', 'approved_by', 'approved_at'])
        elif duplicate.status == TeamSeasonKitType.STATUS_APPROVED and row.status == TeamSeasonKitType.STATUS_APPROVED:
            if duplicate.approved_by_id is None and row.approved_by_id is not None:
                duplicate.approved_by = row.approved_by
                update_fields.append('approved_by')
            if duplicate.approved_at is None and row.approved_at is not None:
                duplicate.approved_at = row.approved_at
                update_fields.append('approved_at')

        if duplicate.created_by_id is None and row.created_by_id is not None:
            duplicate.created_by = row.created_by
            update_fields.append('created_by')

        if source_priority.get(row.source, 0) > source_priority.get(duplicate.source, 0):
            duplicate.source = row.source
            update_fields.append('source')

        if update_fields:
            duplicate.save(update_fields=list(dict.fromkeys(update_fields)))

        row.delete()
        reconciled_team_season_types += 1

    return moved_team_season_types, reconciled_team_season_types


def validate_team_merge(source_team, target_team):
    if source_team.id == target_team.id:
        raise ValidationError({'target_team_id': 'Source and target teams must differ.'})

    if source_team.is_verified:
        raise TeamModerationConflict('Verified source teams cannot be merged through this moderation flow.')

    if not target_team.is_verified:
        raise ValidationError({'target_team_id': 'Target team must be verified.'})


def approve_team(*, team_id, actor):
    with transaction.atomic():
        team = Team.objects.select_for_update().select_related('league').get(pk=team_id)

        if team.is_verified:
            raise TeamModerationConflict('This team has already been verified.')

        previous_state = {
            'source_team': snapshot_team(team),
        }

        team.is_verified = True
        team.save(update_fields=['is_verified'])

        action = build_team_moderation_action(
            actor=actor,
            action_type=TeamModerationAction.ACTION_APPROVE,
            source_team=team,
            previous_state=previous_state,
            resulting_state={'source_team': snapshot_team(team)},
            summary={'approved': True},
            is_reversible=True,
        )

        return team, action


def merge_teams_safely(*, source_team_id, target_team_id, actor):
    with transaction.atomic():
        source_team = Team.objects.select_for_update().select_related('league').get(pk=source_team_id)
        target_team = Team.objects.select_for_update().select_related('league').get(pk=target_team_id)

        validate_team_merge(source_team, target_team)

        previous_state = {
            'source_team': snapshot_team(source_team),
            'target_team': snapshot_team(target_team),
        }

        moved_kits = 0
        merged_duplicate_kits = 0
        moved_userkits = 0

        target_kits = list(
            Kit.objects.select_for_update().filter(team=target_team).order_by('id')
        )
        target_lookup = {
            get_kit_duplicate_key(kit): kit
            for kit in target_kits
        }

        source_kits = list(
            Kit.objects.select_for_update().filter(team=source_team).order_by('id')
        )
        for source_kit in source_kits:
            key = get_kit_duplicate_key(source_kit)
            canonical_target_kit = target_lookup.get(key)

            if canonical_target_kit is None:
                source_kit.team = target_team
                source_kit.save(update_fields=['team'])
                target_lookup[key] = source_kit
                moved_kits += 1
                continue

            merge_kit_metadata(source_kit, canonical_target_kit)
            moved_userkits += UserKit.objects.filter(kit=source_kit).update(kit=canonical_target_kit)
            source_kit.delete()
            merged_duplicate_kits += 1

        moved_wishlist_items, deduplicated_wishlist_items = reconcile_wishlist_items(
            source_team,
            target_team,
        )
        updated_favorite_profiles = Profile.objects.filter(favorite_team=source_team).update(
            favorite_team=target_team,
        )
        moved_team_season_types, reconciled_team_season_types = reconcile_team_season_rows(
            source_team,
            target_team,
        )

        source_team_snapshot = snapshot_team(source_team)
        source_team.delete()

        summary = {
            'merged': True,
            'source_team_id': source_team_snapshot['id'],
            'source_team_slug': source_team_snapshot['slug'],
            'moved_kits': moved_kits,
            'merged_duplicate_kits': merged_duplicate_kits,
            'moved_userkits': moved_userkits,
            'moved_wishlist_items': moved_wishlist_items,
            'deduplicated_wishlist_items': deduplicated_wishlist_items,
            'updated_favorite_profiles': updated_favorite_profiles,
            'moved_team_season_types': moved_team_season_types,
            'reconciled_team_season_types': reconciled_team_season_types,
        }

        action = build_team_moderation_action(
            actor=actor,
            action_type=TeamModerationAction.ACTION_MERGE,
            source_team=Team(id=source_team_snapshot['id'], name=source_team_snapshot['name']),
            target_team=target_team,
            previous_state=previous_state,
            resulting_state={'target_team': snapshot_team(target_team)},
            summary=summary,
            is_reversible=False,
            undo_block_reason=TEAM_MERGE_UNDO_BLOCK_REASON,
        )

        return target_team, action, summary


def reject_unused_team(*, team_id, actor):
    with transaction.atomic():
        team = Team.objects.select_for_update().select_related('league').get(pk=team_id)

        if team.is_verified:
            raise TeamModerationConflict('Verified teams cannot be rejected through this moderation flow.')

        usage = get_team_usage(team)
        if not usage.is_unused():
            raise TeamModerationConflict({
                'detail': 'This team is in use and cannot be rejected. Merge it into an existing team instead.',
                'code': 'team_in_use',
                'usage': usage.as_dict(),
            })

        previous_state = {
            'source_team': snapshot_team(team),
        }
        source_team_snapshot = previous_state['source_team']
        team.delete()

        action = build_team_moderation_action(
            actor=actor,
            action_type=TeamModerationAction.ACTION_REJECT,
            source_team=Team(id=source_team_snapshot['id'], name=source_team_snapshot['name']),
            previous_state=previous_state,
            resulting_state={'deleted': True},
            summary={'deleted': True, 'usage': usage.as_dict()},
            is_reversible=False,
            undo_block_reason=TEAM_REJECT_UNDO_BLOCK_REASON,
        )

        return source_team_snapshot, action
