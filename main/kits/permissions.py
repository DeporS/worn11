from rest_framework import permissions
from django.utils.dateparse import parse_datetime


def _snapshot_team_season_kit_type(row):
    return {
        'id': row.id,
        'status': row.status,
        'approved_by_id': row.approved_by_id,
        'approved_at': row.approved_at.isoformat() if row.approved_at else None,
    }


def _snapshot_kit_type(kit_type):
    return {
        'id': kit_type.id,
        'status': kit_type.status,
        'approved_by_id': kit_type.approved_by_id,
        'approved_at': kit_type.approved_at.isoformat() if kit_type.approved_at else None,
        'merged_into_id': kit_type.merged_into_id,
    }


def _deserialize_datetime(value):
    if not value:
        return None
    return parse_datetime(value)


def is_staff_or_moderator(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_staff or user.is_superuser:
        return True

    profile = getattr(user, 'profile', None)
    return bool(profile and profile.is_moderator)


def can_undo_moderation_action(user, action):
    if not user or not user.is_authenticated:
        return False

    if user.is_staff or user.is_superuser:
        return True

    profile = getattr(user, 'profile', None)
    return bool(profile and profile.is_moderator and action.actor_id == user.id)


def moderation_action_is_currently_undoable(action):
    from .models import KitType, TeamSeasonKitType, KitTypeModerationAction

    if action.undone_at is not None:
        return False, 'already_undone'

    if not action.is_reversible:
        return False, action.undo_block_reason or 'not_reversible'

    if action.action_type == KitTypeModerationAction.ACTION_MERGE:
        return False, action.undo_block_reason or 'not_reversible'

    if action.team_season_kit_type_id is None or action.source_kit_type_id is None:
        return False, 'missing_references'

    try:
        suggestion = TeamSeasonKitType.objects.select_related('kit_type').get(pk=action.team_season_kit_type_id)
        source_kit_type = KitType.objects.get(pk=action.source_kit_type_id)
    except (TeamSeasonKitType.DoesNotExist, KitType.DoesNotExist):
        return False, 'missing_references'

    expected_suggestion = action.resulting_state.get('team_season_kit_type') or {}
    expected_source_type = action.resulting_state.get('source_kit_type') or {}

    current_suggestion = _snapshot_team_season_kit_type(suggestion)
    current_source_type = _snapshot_kit_type(source_kit_type)
    current_source_type['merged_into_id'] = source_kit_type.merged_into_id

    if expected_suggestion and current_suggestion != expected_suggestion:
        return False, 'state_conflict'

    if expected_source_type and current_source_type != expected_source_type:
        return False, 'state_conflict'

    return True, ''


class IsStaffOrModerator(permissions.BasePermission):
    message = 'You do not have permission to access this resource.'

    def has_permission(self, request, view):
        return is_staff_or_moderator(request.user)
