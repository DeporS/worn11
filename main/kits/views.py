from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.pagination import PageNumberPagination

from rest_framework.throttling import ScopedRateThrottle
from .throttles import KitCreationThrottle

from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Sum, Count, Exists, OuterRef, Value, BooleanField, Prefetch, Q, Subquery
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from urllib.parse import urlencode
import re

from .models import League, UserKit, UserKitImage, WishlistItem, Kit, KitType, KitTypeAlias, TeamSeasonKitType, KitTypeModerationAction, TeamModerationAction, ShirtVersion, SIZE_CHOICES, CONDITION_CHOICES, SHIRT_TECHNOLOGIES, SHIRT_TYPES, Team, Profile, Country, Follow, KitComment, KitCommentLike, KitReport, Conversation, Message, Notification, CollectionValueSnapshot, calculate_collection_total_value, record_collection_value_snapshot, build_team_slug, normalize_wishlist_kit_type
from .permissions import IsStaffOrModerator, can_undo_moderation_action, moderation_action_is_currently_undoable, is_staff_or_moderator
from .serializers import LeagueSerializer, UserKitSerializer, WishlistItemSerializer, WishlistToggleSerializer, KitSerializer, TeamSerializer, UserSearchSerializer, ProfileSerializer, UserSerializer, UserStatsProfileSerializer, CountrySerializer, KitCommentSerializer, KitCommentWriteSerializer, KitReportSerializer, ConversationListSerializer, ConversationDetailSerializer, ConversationStartSerializer, MessageSerializer, MessageWriteSerializer, KitSearchSuggestionSerializer, NotificationSerializer, CollectionValueSnapshotSerializer, AdminKitTypeSuggestionSerializer, AdminKitTypeMergeSerializer, TeamModerationListSerializer, TeamModerationMergeSerializer, TeamModerationActionSerializer, KitTypeModerationActionSerializer, ApprovedTeamSeasonKitTypeSerializer, normalize_catalog_name, AdminCountryCreateSerializer, AdminLeagueCreateSerializer, TeamModerationApproveSerializer, TeamModerationDeleteContentSerializer
from .team_moderation import TeamModerationConflict, TEAM_MERGE_UNDO_BLOCK_REASON, TEAM_REJECT_UNDO_BLOCK_REASON, approve_team, build_team_reject_block_reason, delete_team_and_associated_content, get_team_usage, merge_teams_safely, normalize_team_name_for_matching, reject_unused_team, team_name_tokens


SUPPORTED_KIT_TYPES = [
    'Home',
    'Away',
    'Third',
    'Goalkeeper',
    'Fourth',
    'Cup',
    'Training',
    'Special',
]

MIN_SEASON_START_YEAR = 1940
FREE_WISHLIST_LIMIT = 10

KIT_TYPE_ALIASES = {
    'home': 'Home',
    'away': 'Away',
    'third': 'Third',
    'goalkeeper': 'Goalkeeper',
    'gk': 'Goalkeeper',
    'keeper': 'Goalkeeper',
    'goalie': 'Goalkeeper',
    'fourth': 'Fourth',
    'cup': 'Cup',
    'training': 'Training',
    'special': 'Special',
    'special edition': 'Special',
}

KIT_TYPE_ORDER = {
    kit_type: index for index, kit_type in enumerate(SUPPORTED_KIT_TYPES)
}


def get_wishlist_limit(user):
    if getattr(getattr(user, 'profile', None), 'is_pro', False):
        return None
    return FREE_WISHLIST_LIMIT

EXACT_SEASON_PATTERN = re.compile(r'\b(\d{4})\s*/\s*(\d{4})\b')
SHORT_SEASON_PATTERN = re.compile(r'\b(\d{2})\s*/\s*(\d{2})\b')
SPACE_SEASON_PATTERN = re.compile(r'(?<!\d)(\d{2}|\d{4})\s+(\d{2}|\d{4})(?!\d)')
SEASON_PREFIX_PATTERN = re.compile(r'(?<!\d)(\d{2}|\d{4})\s*/\s*(\d{0,4})(?!\d)')
SPACE_SEASON_PREFIX_PATTERN = re.compile(r'(?<!\d)(\d{2}|\d{4})\s+(\d{1,4})(?!\d)')
YEAR_PATTERN = re.compile(r'\b(19|20)\d{2}\b')
YEAR_FRAGMENT_PATTERN = re.compile(r'\b\d{1,4}\b')


def normalize_search_query(value):
    return ' '.join((value or '').strip().split())


def get_full_year_from_token(token):
    if len(token) == 4:
        return int(token)
    if len(token) == 2:
        return get_likely_full_year_from_two_digit_token(token)
    return None


def get_likely_full_year_from_two_digit_token(token):
    if len(token) != 2 or not token.isdigit():
        return None

    upcoming_year_two_digits = (timezone.now().year + 1) % 100
    token_value = int(token)

    if token_value <= upcoming_year_two_digits:
        return 2000 + token_value

    return 1900 + token_value


def normalize_year_fragment(token):
    cleaned_token = (token or '').strip()
    if len(cleaned_token) != 2 or not cleaned_token.isdigit():
        return cleaned_token

    if cleaned_token in {'19', '20'}:
        return cleaned_token

    likely_year = get_likely_full_year_from_two_digit_token(cleaned_token)
    return str(likely_year) if likely_year is not None else cleaned_token


def normalize_season_tokens(start_token, end_token):
    start_year = get_full_year_from_token(start_token)
    if start_year is None:
        return None

    if len(end_token) == 4:
        end_year = int(end_token)
    elif len(end_token) == 2:
        century = (start_year // 100) * 100
        end_year = century + int(end_token)
        if end_year < start_year:
            end_year += 100
    else:
        return None

    return f"{start_year}/{end_year}"


def is_exact_season_pair_tokens(start_token, end_token):
    if not start_token or not end_token:
        return False

    if len(start_token) == 2 and len(end_token) == 2:
        return True

    if len(start_token) == 4 and len(end_token) == 4:
        return True

    if len(start_token) == 4 and len(end_token) == 2:
        start_year = int(start_token)
        expected_end_suffix = str((start_year + 1) % 100).zfill(2)
        return end_token == expected_end_suffix

    return False


def normalize_season_prefix(start_token, end_fragment):
    start_year = get_full_year_from_token(start_token)
    if start_year is None:
        return None

    cleaned_end_fragment = (end_fragment or '').strip()
    return f"{start_year}/{cleaned_end_fragment}"


def get_matching_kit_types_for_prefix(type_fragment):
    normalized_fragment = (type_fragment or '').strip().lower()
    if not normalized_fragment:
        return []

    matched_types = []
    for kit_type in SUPPORTED_KIT_TYPES:
        if kit_type.lower().startswith(normalized_fragment):
            matched_types.append(kit_type)

    for alias, canonical_type in KIT_TYPE_ALIASES.items():
        if alias.startswith(normalized_fragment) and canonical_type not in matched_types:
            matched_types.append(canonical_type)

    return sorted(matched_types, key=get_kit_type_order)


def extract_trailing_kit_type(query):
    normalized_query = normalize_search_query(query)
    if not normalized_query:
        return normalized_query, []

    lowered_query = normalized_query.lower()
    for alias, canonical_type in sorted(KIT_TYPE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        suffix = f" {alias}"
        if lowered_query == alias or lowered_query.endswith(suffix):
            trimmed_query = normalized_query[: -len(alias)].strip()
            return trimmed_query, [canonical_type]

    tokens = normalized_query.split()
    if not tokens:
        return normalized_query, []

    trailing_token = tokens[-1]
    matched_types = get_matching_kit_types_for_prefix(trailing_token)
    if matched_types:
        return normalize_search_query(' '.join(tokens[:-1])), matched_types

    return normalized_query, []


def parse_kit_search_query(query):
    normalized_query = normalize_search_query(query)

    parsed = {
        'normalized_query': normalized_query,
        'team_text': normalized_query,
        'kit_types': [],
        'exact_season': None,
        'season_prefix': None,
        'year_fragment': None,
    }

    if not normalized_query:
        parsed['team_text'] = ''
        return parsed

    normalized_query, matched_kit_types = extract_trailing_kit_type(normalized_query)
    parsed['kit_types'] = matched_kit_types

    exact_season_match = EXACT_SEASON_PATTERN.search(normalized_query)
    if exact_season_match:
        start_year, end_year = exact_season_match.groups()
        parsed['exact_season'] = f"{start_year}/{end_year}"
        normalized_query = EXACT_SEASON_PATTERN.sub(' ', normalized_query, count=1)
    else:
        short_season_match = SHORT_SEASON_PATTERN.search(normalized_query)
        if short_season_match:
            start_year, end_year = short_season_match.groups()
            parsed['exact_season'] = normalize_season_tokens(start_year, end_year)
            normalized_query = SHORT_SEASON_PATTERN.sub(' ', normalized_query, count=1)
        else:
            space_season_match = SPACE_SEASON_PATTERN.search(normalized_query)
            if space_season_match:
                start_year, end_year = space_season_match.groups()
                normalized_season = normalize_season_tokens(start_year, end_year)
                if normalized_season and is_exact_season_pair_tokens(start_year, end_year):
                    parsed['exact_season'] = normalized_season
                    normalized_query = SPACE_SEASON_PATTERN.sub(' ', normalized_query, count=1)

    if not parsed['exact_season']:
        season_prefix_match = SEASON_PREFIX_PATTERN.search(normalized_query)
        if season_prefix_match:
            start_year, end_fragment = season_prefix_match.groups()
            normalized_prefix = normalize_season_prefix(start_year, end_fragment)
            if normalized_prefix and end_fragment != '':
                parsed['season_prefix'] = normalized_prefix
                normalized_query = SEASON_PREFIX_PATTERN.sub(' ', normalized_query, count=1)
            elif normalized_prefix and normalized_query.find('/') != -1:
                parsed['season_prefix'] = normalized_prefix
                normalized_query = SEASON_PREFIX_PATTERN.sub(' ', normalized_query, count=1)
        else:
            space_season_prefix_match = SPACE_SEASON_PREFIX_PATTERN.search(normalized_query)
            if space_season_prefix_match:
                start_year, end_fragment = space_season_prefix_match.groups()
                normalized_prefix = normalize_season_prefix(start_year, end_fragment)
                if normalized_prefix and 0 < len(end_fragment) < 4:
                    parsed['season_prefix'] = normalized_prefix
                    normalized_query = SPACE_SEASON_PREFIX_PATTERN.sub(' ', normalized_query, count=1)

    if not parsed['exact_season'] and not parsed['season_prefix']:
        year_match = YEAR_PATTERN.search(normalized_query)
        if year_match:
            parsed['year_fragment'] = year_match.group(0)
            normalized_query = YEAR_PATTERN.sub(' ', normalized_query, count=1)
        else:
            year_fragment_match = YEAR_FRAGMENT_PATTERN.search(normalized_query)
            if year_fragment_match:
                parsed['year_fragment'] = normalize_year_fragment(year_fragment_match.group(0))
                normalized_query = YEAR_FRAGMENT_PATTERN.sub(' ', normalized_query, count=1)

    parsed['team_text'] = normalize_search_query(normalized_query)
    return parsed


def parse_season_years(season):
    season_text = (season or '').strip()
    if not season_text:
        return []

    parts = re.findall(r'\d{2,4}', season_text)
    if len(parts) < 2:
        return []

    first_part, second_part = parts[0], parts[1]

    start_year = get_full_year_from_token(first_part)
    if start_year is None:
        return []

    if len(second_part) == 4:
        end_year = int(second_part)
    elif len(second_part) == 2:
        century = (start_year // 100) * 100
        end_year = century + int(second_part)
        if end_year < start_year:
            end_year += 100
    else:
        return []

    return [start_year, end_year]


def normalize_season_value(season):
    season_years = parse_season_years(season)
    if len(season_years) == 2:
        return f"{season_years[0]}/{season_years[1]}"
    return normalize_search_query(season)


def season_matches_exact(season, exact_season):
    if not exact_season:
        return False
    return normalize_season_value(season) == normalize_season_value(exact_season)


def season_matches_prefix(season, season_prefix):
    if not season_prefix:
        return False
    return normalize_season_value(season).startswith(normalize_search_query(season_prefix))


def season_matches_year_fragment(season, year_fragment):
    if not year_fragment:
        return False

    return any(str(year).startswith(year_fragment) for year in parse_season_years(season))


MERGE_UNDO_BLOCK_REASON = 'Merge undo requires manual review.'


def serialize_datetime(value):
    return value.isoformat() if value is not None else None


def deserialize_datetime(value):
    if not value:
        return None
    return parse_datetime(value)


def snapshot_team_season_kit_type(row):
    return {
        'id': row.id,
        'status': row.status,
        'approved_by_id': row.approved_by_id,
        'approved_at': serialize_datetime(row.approved_at),
    }


def snapshot_kit_type(kit_type):
    return {
        'id': kit_type.id,
        'status': kit_type.status,
        'approved_by_id': kit_type.approved_by_id,
        'approved_at': serialize_datetime(kit_type.approved_at),
        'merged_into_id': kit_type.merged_into_id,
    }


def apply_team_season_kit_type_snapshot(row, snapshot):
    row.status = snapshot['status']
    row.approved_by_id = snapshot['approved_by_id']
    row.approved_at = deserialize_datetime(snapshot['approved_at'])
    row.save(update_fields=['status', 'approved_by', 'approved_at'])


def apply_kit_type_snapshot(kit_type, snapshot):
    kit_type.status = snapshot['status']
    kit_type.approved_by_id = snapshot['approved_by_id']
    kit_type.approved_at = deserialize_datetime(snapshot['approved_at'])
    kit_type.merged_into_id = snapshot.get('merged_into_id')
    kit_type.save(update_fields=['status', 'approved_by', 'approved_at', 'merged_into'])


def build_moderation_action_record(*, actor, action_type, suggestion=None, source_kit_type=None, target_kit_type=None, team_name=None, season=None, previous_state=None, resulting_state=None, is_reversible=True, undo_block_reason=''):
    return KitTypeModerationAction.objects.create(
        actor=actor,
        action_type=action_type,
        team_season_kit_type=suggestion,
        source_kit_type=source_kit_type,
        target_kit_type=target_kit_type,
        team_name=team_name if team_name is not None else (suggestion.team.name if suggestion is not None else ''),
        season=season if season is not None else (suggestion.season if suggestion is not None else ''),
        source_kit_type_name=(source_kit_type.name if source_kit_type is not None else ''),
        target_kit_type_name=(target_kit_type.name if target_kit_type is not None else ''),
        previous_state=previous_state or {},
        resulting_state=resulting_state or {},
        is_reversible=is_reversible,
        undo_block_reason=undo_block_reason,
    )


def moderation_action_conflict_response():
    return Response(
        {'detail': 'This action can no longer be safely undone because newer changes exist.'},
        status=status.HTTP_409_CONFLICT,
    )


def get_season_sort_year(season):
    season_years = parse_season_years(season)
    if season_years:
        return season_years[0]
    return 0


def get_team_match_rank(team_name, team_query):
    lowered_name = (team_name or '').lower()
    lowered_query = (team_query or '').lower()

    if not lowered_query:
        return 0
    if lowered_name == lowered_query:
        return 0
    if lowered_name.startswith(lowered_query):
        return 1
    if lowered_query in lowered_name:
        return 2
    return 3


def get_season_match_rank(kit, parsed_query):
    if parsed_query['exact_season']:
        return 0 if season_matches_exact(kit.season, parsed_query['exact_season']) else 1
    if parsed_query['year_fragment']:
        season_years = parse_season_years(kit.season)
        if len(season_years) == 2:
            if str(season_years[0]).startswith(parsed_query['year_fragment']):
                return 0
            if str(season_years[1]).startswith(parsed_query['year_fragment']):
                return 1
        return 2
    return 0


def get_kit_type_order(kit_type):
    normalized_type = (kit_type or '').strip()
    if normalized_type in KIT_TYPE_ORDER:
        return KIT_TYPE_ORDER[normalized_type]
    for prefix, order in KIT_TYPE_ORDER.items():
        if normalized_type.lower().startswith(prefix.lower()):
            return order
    return 99


def build_season_label(start_year):
    return f"{start_year}/{start_year + 1}"


def get_generated_seasons():
    min_start_year = MIN_SEASON_START_YEAR
    max_start_year = timezone.now().year
    return [build_season_label(start_year) for start_year in range(min_start_year, max_start_year + 1)]


def get_generated_suggestion(team, season, kit_type):
    team_slug = build_team_slug(team.name)
    query_string = urlencode({
        'season': season,
        'type': kit_type,
    })
    return {
        'team_id': team.id,
        'team_name': team.name,
        'team_slug': team_slug,
        'season': season,
        'kit_type': kit_type,
        'label': f"{team.name} {season} {kit_type}",
        'url': f"/history/team/{team_slug}/variants?{query_string}",
        'preview_image': None,
        'has_uploads': False,
    }


def get_generated_season_match_rank(season, parsed_query):
    if parsed_query['exact_season']:
        return 0 if season_matches_exact(season, parsed_query['exact_season']) else 1
    if parsed_query['season_prefix']:
        return 0 if season_matches_prefix(season, parsed_query['season_prefix']) else 1
    if parsed_query['year_fragment']:
        season_years = parse_season_years(season)
        if len(season_years) == 2:
            if str(season_years[0]).startswith(parsed_query['year_fragment']):
                return 0
            if str(season_years[1]).startswith(parsed_query['year_fragment']):
                return 1
        return 2
    return 0


def get_history_type_filter(kit_type):
    normalized_type = normalize_search_query(kit_type)

    if normalized_type == 'Goalkeeper':
        return Q(kit__kit_type__iexact='GK') | Q(kit__kit_type__iexact='Goalkeeper')

    if normalized_type == 'Special':
        return Q(kit__kit_type__iexact='Special') | Q(kit__kit_type__istartswith='Special')

    return Q(kit__kit_type__iexact=normalized_type)


def get_upload_preview_type_filter(kit_type):
    normalized_type = normalize_search_query(kit_type)

    if normalized_type == 'Goalkeeper':
        return Q(user_kit__kit__kit_type__iexact='GK') | Q(user_kit__kit__kit_type__iexact='Goalkeeper')

    if normalized_type == 'Special':
        return Q(user_kit__kit__kit_type__iexact='Special') | Q(user_kit__kit__kit_type__istartswith='Special')

    return Q(user_kit__kit__kit_type__iexact=normalized_type)


def normalize_stored_kit_type(kit_type):
    normalized_type = normalize_search_query(kit_type)

    if normalized_type in {'GK', 'Goalkeeper'}:
        return 'Goalkeeper'

    if normalized_type.lower().startswith('special'):
        return 'Special'

    return normalized_type


def get_wishlist_type_filter(kit_type):
    normalized_type = normalize_wishlist_kit_type(kit_type)

    if normalized_type == 'Goalkeeper':
        return Q(kit__kit_type__iexact='GK') | Q(kit__kit_type__iexact='Goalkeeper')

    if normalized_type == 'Special':
        return Q(kit__kit_type__iexact='Special') | Q(kit__kit_type__istartswith='Special')

    return Q(kit__kit_type__iexact=normalized_type)


def build_wishlist_preview_map(items, request=None):
    wishlist_items = list(items)
    if not wishlist_items:
        return {}

    team_ids = {item.team_id for item in wishlist_items}
    seasons = {item.season for item in wishlist_items}
    requested_types = {item.kit_type for item in wishlist_items}

    type_filter = Q()
    for requested_type in requested_types:
        type_filter |= get_wishlist_type_filter(requested_type)

    matching_kits = UserKit.objects.filter(
        kit__team_id__in=team_ids,
        kit__season__in=seasons,
    ).filter(
        type_filter
    ).select_related(
        'kit',
        'kit__team',
    ).prefetch_related(
        Prefetch('images', queryset=UserKitImage.objects.order_by('order', 'created_at', 'id'), to_attr='ordered_preview_images')
    ).annotate(
        likes_count=Count('likes', distinct=True),
    ).order_by(
        'kit__team_id',
        'kit__season',
        '-likes_count',
        '-added_at',
        'id',
    )

    preview_map = {}
    for user_kit in matching_kits:
        preview_key = (
            user_kit.kit.team_id,
            user_kit.kit.season,
            normalize_wishlist_kit_type(user_kit.kit.kit_type),
        )
        if preview_key in preview_map:
            continue

        preview_image = next(iter(getattr(user_kit, 'ordered_preview_images', [])), None)
        if preview_image is None:
            continue

        preview_url = preview_image.image.url
        if request is not None:
            preview_url = request.build_absolute_uri(preview_url)

        preview_map[preview_key] = preview_url

    return preview_map


def get_team_by_identifier(team_identifier):
    normalized_identifier = (team_identifier or '').strip()
    if not normalized_identifier:
        return None

    if normalized_identifier.isdigit():
        return Team.objects.select_related('country', 'league').filter(pk=int(normalized_identifier)).first()

    for team in Team.objects.select_related('country', 'league').all().order_by('id'):
        if build_team_slug(team.name) == normalized_identifier:
            return team

    return None


def get_comment_like_annotation(user):
    if user.is_authenticated:
        return Exists(
            KitCommentLike.objects.filter(comment_id=OuterRef('pk'), user=user)
        )

    return Value(False, output_field=BooleanField())


def get_comment_base_queryset(user):
    return KitComment.objects.select_related(
        'user',
        'user__profile',
        'kit',
        'parent',
        'parent__user',
        'reply_to',
        'reply_to__user',
    ).annotate(
        likes_count=Count('comment_likes', distinct=True),
        is_liked_by_me=get_comment_like_annotation(user),
        reply_count=Count('replies', distinct=True),
    )


def get_top_level_comments_queryset(user):
    replies_queryset = get_comment_base_queryset(user).filter(parent__isnull=False)

    return get_comment_base_queryset(user).filter(parent__isnull=True).prefetch_related(
        Prefetch('replies', queryset=replies_queryset, to_attr='prefetched_replies')
    )


def get_user_conversations_queryset(user):
    latest_message_queryset = Message.objects.filter(
        conversation_id=OuterRef('pk')
    ).order_by('-created_at')
    unread_messages_queryset = Message.objects.filter(
        conversation_id=OuterRef('pk'),
        read_at__isnull=True,
    ).exclude(
        sender=user,
    )

    return Conversation.objects.filter(
        Q(participant_one=user) | Q(participant_two=user)
    ).select_related(
        'participant_one',
        'participant_one__profile',
        'participant_two',
        'participant_two__profile',
    ).annotate(
        last_message_preview=Subquery(latest_message_queryset.values('body')[:1]),
        last_message_created_at=Subquery(latest_message_queryset.values('created_at')[:1]),
        unread_count=Count('messages', filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=user), distinct=True),
    )


def get_user_notifications_queryset(user):
    notification_preview_images = UserKitImage.objects.order_by('order', 'created_at', 'id')

    return Notification.objects.filter(
        recipient=user,
    ).select_related(
        'actor',
        'actor__profile',
        'kit',
        'kit__user',
        'kit__kit',
        'kit__kit__team',
        'comment',
        'comment__user',
    ).prefetch_related(
        Prefetch('kit__images', queryset=notification_preview_images, to_attr='prefetched_notification_images')
    )


def get_public_user_kits_queryset():
    return UserKit.objects.filter(
        in_the_collection=True,
    ).select_related(
        'kit',
        'kit__team',
        'kit__kit_type_ref',
        'shirt_version',
        'user',
    ).prefetch_related(
        'images',
        'likes',
    ).annotate(
        likes_count=Count('likes', distinct=True),
        comments_count=Count('comments', distinct=True),
    )


def get_following_feed_queryset(user):
    followed_user_ids = Follow.objects.filter(
        follower=user
    ).values_list(
        'following_id',
        flat=True,
    )

    return UserKit.objects.filter(
        user_id__in=followed_user_ids,
    ).exclude(
        user=user,
    ).select_related(
        'kit',
        'kit__team',
        'kit__kit_type_ref',
        'shirt_version',
        'user',
        'user__profile',
    ).prefetch_related(
        'images',
        'likes',
    ).annotate(
        likes_count=Count('likes', distinct=True),
        comments_count=Count('comments', distinct=True),
    ).order_by(
        '-added_at',
        '-id',
    )

# Current user
class CurrentUserAPI(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

# Pagination configuration
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

# Endpoint: My collection + adding new kits
class MyCollectionAPI(generics.ListCreateAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [IsAuthenticated] # Only for logged in users

    throttle_classes = [KitCreationThrottle] # Custom throttle for kit creation based on user plan - Pro 50 create/day, Free 5 create/day

    def get_queryset(self):
        # Return only kits of the logged-in user
        return UserKit.objects.filter(user=self.request.user)\
            .select_related('kit', 'kit__team', 'kit__kit_type_ref', 'shirt_version')\
            .annotate(likes_count=Count('likes', distinct=True), comments_count=Count('comments', distinct=True))\
            .order_by('-added_at')
    
    # Override to check pro limits and file uploads safety
    def create(self, request, *args, **kwargs):

        images = request.FILES.getlist('images')

        user = request.user
        is_pro = False
        if hasattr(user, 'profile'):
            is_pro = user.profile.is_pro
        
        limit = 20 if is_pro else 5

        # Business logic bypass check
        if len(images) > limit:
            raise ValidationError({
                "images": [f"Upload limit exceeded. You are allowed {limit} photos. You sent {len(images)}."]
            })
        
        # Malicious file upload check
        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/heic']

        for img in images:

            # Check content type
            if img.content_type not in allowed_types:
                raise ValidationError({
                    "images": [f"Unsupported file type: {img.content_type}. Allowed types are: JPEG, PNG, WEBP, HEIC."]
                })
            
            # Check file size (max 10MB)
            if img.size > 10 * 1024 * 1024:
                raise ValidationError({
                    "images": [f"File too large: {img.name}. Maximum allowed size is 10MB."]
                })
            
        return super().create(request, *args, **kwargs)


    def perform_create(self, serializer):
        # Automatically assign the logged-in user on save
        user_kit = serializer.save(user=self.request.user)
        record_collection_value_snapshot(
            self.request.user,
            CollectionValueSnapshot.REASON_KIT_ADDED,
            related_userkit=user_kit,
        )

# Endpoint: Detail, update, delete for a specific kit in collection
class MyCollectionDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserKit.objects.filter(user=self.request.user)\
            .select_related('kit', 'kit__team', 'kit__kit_type_ref', 'shirt_version')\
            .prefetch_related('images')\
            .annotate(likes_count=Count('likes', distinct=True), comments_count=Count('comments', distinct=True))\
            .order_by('-added_at')

    def perform_update(self, serializer):
        instance = self.get_object()
        previous_state = {
            'manual_value': instance.manual_value,
            'in_the_collection': instance.in_the_collection,
            'kit_id': instance.kit_id,
            'size': instance.size,
            'condition': instance.condition,
            'shirt_technology': instance.shirt_technology,
            'shirt_version_id': instance.shirt_version_id,
        }

        updated_instance = serializer.save()

        if previous_state['in_the_collection'] != updated_instance.in_the_collection:
            reason = CollectionValueSnapshot.REASON_COLLECTION_STATUS_CHANGED
        elif previous_state['manual_value'] != updated_instance.manual_value:
            reason = CollectionValueSnapshot.REASON_VALUE_UPDATED
        elif previous_state['kit_id'] != updated_instance.kit_id:
            reason = CollectionValueSnapshot.REASON_KIT_UPDATED
        elif (
            previous_state['size'] != updated_instance.size
            or previous_state['condition'] != updated_instance.condition
            or previous_state['shirt_technology'] != updated_instance.shirt_technology
            or previous_state['shirt_version_id'] != updated_instance.shirt_version_id
        ):
            reason = CollectionValueSnapshot.REASON_VALUE_UPDATED
        else:
            reason = None

        if reason is not None:
            record_collection_value_snapshot(
                self.request.user,
                reason,
                related_userkit=updated_instance,
            )

    def perform_destroy(self, instance):
        user = instance.user
        super().perform_destroy(instance)
        record_collection_value_snapshot(
            user,
            CollectionValueSnapshot.REASON_KIT_REMOVED,
        )

# Endpoint: Show other user's collection
class UserCollectionAPI(generics.ListAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [permissions.AllowAny] # Publicly accessible

    def get_queryset(self):
        # Get username from URL
        username = self.kwargs['username']

        # Return kits of the specified user
        return UserKit.objects.filter(user__username=username)\
            .select_related('kit', 'kit__team', 'kit__kit_type_ref', 'shirt_version')\
            .prefetch_related('images')\
            .annotate(likes_count=Count('likes', distinct=True), comments_count=Count('comments', distinct=True))\
            .order_by('-added_at')


# Endpoint: Public detail for a specific user kit
class PublicUserKitDetailAPI(generics.RetrieveAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [permissions.AllowAny]
    lookup_url_kwarg = 'userkit_id'

    def get_queryset(self):
        return get_public_user_kits_queryset()


class ExploreKitsAPI(generics.ListAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        sort = self.request.query_params.get('sort', 'trending').strip().lower()
        limit = self.request.query_params.get('limit', '24')

        try:
            limit_value = int(limit)
        except (TypeError, ValueError):
            limit_value = 24

        limit_value = max(1, min(limit_value, 60))

        queryset = get_public_user_kits_queryset()

        if sort == 'latest':
            queryset = queryset.order_by('-added_at')
        elif sort == 'most_liked':
            queryset = queryset.order_by('-likes_count', '-comments_count', '-added_at')
        elif sort == 'for_sale':
            queryset = queryset.filter(for_sale=True).order_by('-added_at')
        else:
            queryset = queryset.order_by('-likes_count', '-comments_count', '-added_at')

        return queryset[:limit_value]


class FollowingFeedAPI(APIView):
    permission_classes = [IsAuthenticated]
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 50

    def _get_limit(self, request):
        raw_limit = request.query_params.get('limit')
        if raw_limit is None:
            return self.DEFAULT_LIMIT

        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return self.DEFAULT_LIMIT

        if limit <= 0:
            return self.DEFAULT_LIMIT

        return min(limit, self.MAX_LIMIT)

    def get(self, request):
        queryset = get_following_feed_queryset(request.user)
        limit = self._get_limit(request)
        before = request.query_params.get('before')

        if before is not None:
            try:
                before_id = int(before)
            except (TypeError, ValueError):
                return Response(
                    {'before': ['before must be a valid kit id.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            anchor_kit = queryset.filter(pk=before_id).first()
            if anchor_kit is None:
                return Response(
                    {'before': ['Kit not found in feed.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = queryset.filter(
                Q(added_at__lt=anchor_kit.added_at) |
                Q(added_at=anchor_kit.added_at, id__lt=anchor_kit.id)
            )

        items = list(queryset[:limit])

        if items:
            oldest_item = items[-1]
            has_more = queryset.filter(
                Q(added_at__lt=oldest_item.added_at) |
                Q(added_at=oldest_item.added_at, id__lt=oldest_item.id)
            ).exists()
        else:
            has_more = False

        serializer = UserKitSerializer(items, many=True, context={'request': request})
        return Response({
            'results': serializer.data,
            'has_more': has_more,
        })

# Endpoint: Catalog of all available kits (e.g., for selection when adding)
class KitCatalogAPI(generics.ListAPIView):
    queryset = Kit.objects.select_related('team', 'kit_type_ref').all()
    serializer_class = KitSerializer

# Endpoint: Get options for kit attributes
class KitOptionsView(APIView):
    def get(self, request):
        kit_types = KitType.objects.filter(status=KitType.STATUS_APPROVED).order_by('sort_order', 'name', 'id')
        shirt_versions = ShirtVersion.objects.filter(is_active=True).order_by('sort_order', 'name', 'id')

        return Response({
            "sizes": [{'value': key, 'label': label} for key, label in SIZE_CHOICES],
            "conditions": [{'value': key, 'label': label} for key, label in CONDITION_CHOICES],
            "technologies": [{'value': key, 'label': label} for key, label in SHIRT_TECHNOLOGIES],
            "types": [{'value': key, 'label': label} for key, label in SHIRT_TYPES],
            "kit_types": [
                {
                    'id': kit_type.id,
                    'name': kit_type.name,
                    'slug': kit_type.slug,
                    'canonical_code': kit_type.canonical_code,
                    'category': kit_type.category,
                    'default_visibility': kit_type.default_visibility,
                    'sort_order': kit_type.sort_order,
                }
                for kit_type in kit_types
            ],
            "shirt_versions": [
                {
                    'id': version.id,
                    'code': version.code,
                    'name': version.name,
                    'description': version.description,
                    'manual_value_recommended': version.manual_value_recommended,
                    'valuation_note': version.valuation_note,
                    'sort_order': version.sort_order,
                }
                for version in shirt_versions
            ],
        })


class TeamSearchAPI(generics.ListAPIView):
    serializer_class = TeamSerializer

    throttle_classes = [ScopedRateThrottle] # General throttling based on settings.py
    throttle_scope = 'team_search'

    def get_queryset(self):
        # Get search query from URL parameters e.g., /api/teams/search/?q=Bar
        query = self.request.query_params.get('q', '')

        if len(query) < 3:
            return Team.objects.none()  # Return empty queryset for short queries

        return Team.objects.filter(
            name__icontains=query,
            is_verified=True
        ).select_related(
            'country',
            'league',
        )[:5] # Limit to 5 results


class TeamResolveAPI(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, team_identifier):
        team = get_team_by_identifier(team_identifier)
        if team is None:
            return Response({'detail': 'Team not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TeamSerializer(team)
        return Response(serializer.data)


def get_similar_verified_teams_for_source(source_team, verified_teams, limit=5):
    source_normalized = normalize_team_name_for_matching(source_team.name)
    source_tokens = team_name_tokens(source_team.name)
    scored = []

    for candidate in verified_teams:
        if candidate.id == source_team.id:
            continue

        candidate_normalized = normalize_team_name_for_matching(candidate.name)
        candidate_tokens = team_name_tokens(candidate.name)
        shared_tokens = source_tokens & candidate_tokens
        contains_match = (
            source_normalized in candidate_normalized
            or candidate_normalized in source_normalized
        ) if source_normalized and candidate_normalized else False

        if not shared_tokens and not contains_match:
            continue

        scored.append((
            0 if source_normalized == candidate_normalized else 1,
            -len(shared_tokens),
            0 if contains_match else 1,
            candidate.name.lower(),
            candidate.id,
            candidate,
        ))

    scored.sort()
    return [item[-1] for item in scored[:limit]]


def get_unverified_team_preview_map(teams):
    team_ids = [team.id for team in teams]
    if not team_ids:
        return {}

    preview_images = UserKitImage.objects.filter(
        user_kit__kit__team_id__in=team_ids,
    ).select_related(
        'user_kit__kit',
    ).order_by(
        'user_kit__kit__team_id',
        'order',
        'created_at',
        'id',
    )

    preview_map = {}
    for image in preview_images:
        team_id = image.user_kit.kit.team_id
        if team_id in preview_map:
            continue
        preview_map[team_id] = image.image.url

    return preview_map


class AdminUnverifiedTeamsAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 50

    def get(self, request):
        raw_limit = request.query_params.get('limit', self.DEFAULT_LIMIT)
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT

        limit = max(1, min(limit, self.MAX_LIMIT))
        queryset = Team.objects.filter(
            is_verified=False,
        ).select_related(
            'country',
            'league',
            'league__country',
        ).annotate(
            kits_count=Count('kits', distinct=True),
            userkits_count=Count('kits__owned_by', distinct=True),
            unique_users_count=Count('kits__owned_by__user', distinct=True),
            wishlist_count=Count('wishlist_items', distinct=True),
            favorite_team_count=Count('fans', distinct=True),
            team_season_type_count=Count('season_kit_types', distinct=True),
        ).prefetch_related(
            'kits',
            'season_kit_types',
        ).order_by('id')

        teams = list(queryset[: limit + 1])
        has_more = len(teams) > limit
        teams = teams[:limit]
        preview_map = get_unverified_team_preview_map(teams)
        verified_teams = list(
            Team.objects.filter(is_verified=True).select_related(
                'country',
                'league',
                'league__country',
            ).order_by('name', 'id')
        )

        for team in teams:
            usage = get_team_usage(team)
            seasons = {
                kit.season
                for kit in team.kits.all()
                if (kit.season or '').strip()
            }
            seasons.update(
                row.season
                for row in team.season_kit_types.all()
                if (row.season or '').strip()
            )
            team.seasons = sorted(seasons, key=get_season_sort_year, reverse=True)
            team.preview_image = preview_map.get(team.id)
            team.usage = usage.as_dict()
            team.can_reject = usage.is_unused()
            team.reject_block_reason = '' if team.can_reject else build_team_reject_block_reason(usage)
            team.similar_verified_teams = get_similar_verified_teams_for_source(team, verified_teams)

        serializer = TeamModerationListSerializer(
            teams,
            many=True,
            context={'request': request},
        )
        return Response({
            'results': serializer.data,
            'has_more': has_more,
        })


class AdminTeamApproveAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def post(self, request, team_id):
        team = get_object_or_404(Team, pk=team_id)
        serializer = TeamModerationApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated_team, action = approve_team(
                team_id=team.id,
                actor=request.user,
                name=serializer.validated_data['name'],
                country=serializer.validated_data['country'],
                league=serializer.validated_data['league'],
            )
        except TeamModerationConflict as exc:
            detail = exc.raw_detail if isinstance(exc.raw_detail, dict) else {'detail': exc.raw_detail}
            return Response(detail, status=exc.status_code)

        usage = get_team_usage(updated_team)
        updated_team.kits_count = usage.kits
        updated_team.orphan_kits_count = usage.orphan_kits
        updated_team.userkits_count = usage.userkits
        updated_team.unique_users_count = UserKit.objects.filter(
            kit__team=updated_team,
        ).values('user_id').distinct().count()
        updated_team.wishlist_count = usage.wishlist_items
        updated_team.favorite_team_count = usage.favorite_profiles
        updated_team.usage = usage.as_dict()
        updated_team.seasons = sorted({
            *updated_team.kits.values_list('season', flat=True),
            *updated_team.season_kit_types.values_list('season', flat=True),
        }, key=get_season_sort_year, reverse=True)
        updated_team.preview_image = get_unverified_team_preview_map([updated_team]).get(updated_team.id)
        updated_team.can_reject = usage.is_unused()
        updated_team.reject_block_reason = '' if updated_team.can_reject else build_team_reject_block_reason(usage)
        updated_team.similar_verified_teams = []

        serializer = TeamModerationListSerializer(
            updated_team,
            context={'request': request},
        )
        return Response({
            'team': serializer.data,
            'moderation_action_id': action.id,
        })


class AdminCountriesAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def get(self, request):
        include_inactive = request.query_params.get('include_inactive') == '1'
        queryset = Country.objects.all()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        countries = queryset.order_by('name')
        serializer = CountrySerializer(countries, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AdminCountryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data['name']
        code = serializer.validated_data['code']

        existing_by_name = Country.objects.filter(name__iexact=name).order_by('id').first()
        if existing_by_name is not None:
            return Response({
                'detail': 'A country with this name already exists.',
                'code': 'country_name_conflict',
                'existing_country_id': existing_by_name.id,
            }, status=status.HTTP_409_CONFLICT)

        existing_by_code = Country.objects.filter(code__iexact=code).order_by('id').first()
        if existing_by_code is not None:
            return Response({
                'detail': 'A country with this code already exists.',
                'code': 'country_code_conflict',
                'existing_country_id': existing_by_code.id,
            }, status=status.HTTP_409_CONFLICT)

        country = Country.objects.create(
            name=name,
            code=code,
            is_active=True,
            created_by=request.user,
        )
        response_serializer = CountrySerializer(country)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AdminLeaguesAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def get(self, request):
        queryset = League.objects.filter(is_active=True).select_related('country')
        country_id = request.query_params.get('country_id')
        if country_id not in (None, ''):
            queryset = queryset.filter(country_id=country_id)
        leagues = queryset.order_by('order', 'name')
        serializer = LeagueSerializer(leagues, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AdminLeagueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data['name']
        country = Country.objects.get(pk=serializer.validated_data['country_id'])

        existing_in_country = League.objects.filter(
            country=country,
            name__iexact=name,
        ).order_by('id').first()
        if existing_in_country is not None:
            return Response({
                'detail': 'A league with this name already exists for the selected country.',
                'code': 'league_name_conflict',
                'existing_league_id': existing_in_country.id,
            }, status=status.HTTP_409_CONFLICT)

        existing_global = League.objects.filter(name__iexact=name).order_by('id').first()
        if existing_global is not None:
            return Response({
                'detail': 'A league with this name already exists. Global league-name uniqueness is still enforced in this phase.',
                'code': 'league_global_name_conflict',
                'existing_league_id': existing_global.id,
            }, status=status.HTTP_409_CONFLICT)

        league = League.objects.create(
            name=name,
            country=country,
            is_active=True,
            created_by=request.user,
        )
        response_serializer = LeagueSerializer(league)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AdminTeamMergeAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def post(self, request, team_id):
        serializer = TeamModerationMergeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_team_id = serializer.validated_data['target_team_id']

        source_team = get_object_or_404(Team, pk=team_id)
        target_team = Team.objects.filter(pk=target_team_id).first()
        if target_team is None:
            raise ValidationError({'target_team_id': 'Target team not found.'})

        try:
            merged_target_team, action, summary = merge_teams_safely(
                source_team_id=source_team.id,
                target_team_id=target_team.id,
                actor=request.user,
            )
        except TeamModerationConflict as exc:
            detail = exc.raw_detail if isinstance(exc.raw_detail, dict) else {'detail': exc.raw_detail}
            return Response(detail, status=exc.status_code)

        merged_target_team.kits_count = Kit.objects.filter(team=merged_target_team).count()
        merged_target_team.userkits_count = UserKit.objects.filter(kit__team=merged_target_team).count()
        merged_target_team.unique_users_count = UserKit.objects.filter(
            kit__team=merged_target_team,
        ).values('user_id').distinct().count()
        merged_target_team.wishlist_count = WishlistItem.objects.filter(team=merged_target_team).count()
        merged_target_team.favorite_team_count = Profile.objects.filter(favorite_team=merged_target_team).count()
        merged_target_team.seasons = sorted({
            *merged_target_team.kits.values_list('season', flat=True),
            *merged_target_team.season_kit_types.values_list('season', flat=True),
        }, key=get_season_sort_year, reverse=True)
        merged_target_team.preview_image = get_unverified_team_preview_map([merged_target_team]).get(merged_target_team.id)
        merged_target_team.can_reject = False
        merged_target_team.reject_block_reason = 'Verified teams cannot be rejected through this moderation flow.'
        merged_target_team.similar_verified_teams = []

        target_serializer = TeamModerationListSerializer(
            merged_target_team,
            context={'request': request},
        )
        return Response({
            **summary,
            'target_team': target_serializer.data,
            'moderation_action_id': action.id,
        })


class AdminTeamRejectAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def post(self, request, team_id):
        team = get_object_or_404(Team, pk=team_id)

        try:
            deleted_team, action = reject_unused_team(team_id=team.id, actor=request.user)
        except TeamModerationConflict as exc:
            detail = exc.raw_detail if isinstance(exc.raw_detail, dict) else {'detail': exc.raw_detail}
            return Response(detail, status=exc.status_code)

        return Response({
            'deleted': True,
            'team_id': deleted_team['id'],
            'team_name': deleted_team['name'],
            'moderation_action_id': action.id,
        })


class AdminTeamDeleteContentAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def post(self, request, team_id):
        serializer = TeamModerationDeleteContentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            deleted_team, action, summary = delete_team_and_associated_content(
                team_id=team_id,
                actor=request.user,
                confirmation=serializer.validated_data['confirmation'],
                reason=serializer.validated_data['reason'],
                note=serializer.validated_data.get('note', ''),
            )
        except TeamModerationConflict as exc:
            detail = exc.raw_detail if isinstance(exc.raw_detail, dict) else {'detail': exc.raw_detail}
            return Response(detail, status=exc.status_code)
        except ValidationError as exc:
            detail = exc.detail
            if isinstance(detail, list):
                detail = {'detail': detail}
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'deleted': True,
            'team_id': deleted_team['id'],
            'team_name': deleted_team['name'],
            'summary': summary,
            'moderation_action_id': action.id,
        })


class AdminKitTypeSuggestionsAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def get(self, request):
        suggestions = list(
            TeamSeasonKitType.objects.filter(status=TeamSeasonKitType.STATUS_PENDING)
            .select_related('team', 'kit_type', 'created_by')
            .order_by('-created_at', '-id')
        )

        if suggestions:
            keys = {
                (suggestion.team_id, suggestion.season, suggestion.kit_type_id)
                for suggestion in suggestions
            }
            team_ids = {key[0] for key in keys}
            seasons = {key[1] for key in keys}
            kit_type_ids = {key[2] for key in keys}

            matching_uploads = (
                UserKit.objects.filter(
                    kit__team_id__in=team_ids,
                    kit__season__in=seasons,
                    kit__kit_type_ref_id__in=kit_type_ids,
                )
                .select_related('kit', 'kit__team')
                .prefetch_related('images')
                .order_by('kit__team_id', 'kit__season', 'kit__kit_type_ref_id', '-added_at', '-id')
            )

            upload_count_map = {}
            preview_map = {}
            example_userkit_map = {}
            for user_kit in matching_uploads:
                key = (
                    user_kit.kit.team_id,
                    user_kit.kit.season,
                    user_kit.kit.kit_type_ref_id,
                )
                upload_count_map[key] = upload_count_map.get(key, 0) + 1
                example_userkit_map.setdefault(key, user_kit.id)
                if key not in preview_map:
                    first_image = next(iter(user_kit.images.all()), None)
                    if first_image is not None:
                        preview_map[key] = first_image.image.url

            for suggestion in suggestions:
                key = (suggestion.team_id, suggestion.season, suggestion.kit_type_id)
                suggestion.upload_count = upload_count_map.get(key, 0)
                suggestion.preview_image = preview_map.get(key)
                suggestion.example_source_userkit_id = example_userkit_map.get(key)

        serializer = AdminKitTypeSuggestionSerializer(
            suggestions,
            many=True,
            context={'request': request},
        )
        return Response(serializer.data)


class AdminTeamSeasonKitTypeApproveAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def post(self, request, pk):
        with transaction.atomic():
            suggestion = get_object_or_404(
                TeamSeasonKitType.objects.select_for_update().select_related('kit_type'),
                pk=pk,
            )
            source_kit_type = KitType.objects.select_for_update().get(pk=suggestion.kit_type_id)
            previous_state = {
                'team_season_kit_type': snapshot_team_season_kit_type(suggestion),
                'source_kit_type': snapshot_kit_type(source_kit_type),
            }
            now = timezone.now()

            suggestion.status = TeamSeasonKitType.STATUS_APPROVED
            suggestion.approved_by = request.user
            suggestion.approved_at = now
            suggestion.save(update_fields=['status', 'approved_by', 'approved_at'])

            if source_kit_type.status == KitType.STATUS_PENDING:
                source_kit_type.status = KitType.STATUS_APPROVED
                source_kit_type.approved_by = request.user
                source_kit_type.approved_at = now
                source_kit_type.save(
                    update_fields=['status', 'approved_by', 'approved_at']
                )

            action = build_moderation_action_record(
                actor=request.user,
                action_type=KitTypeModerationAction.ACTION_APPROVE,
                suggestion=suggestion,
                source_kit_type=source_kit_type,
                previous_state=previous_state,
                resulting_state={
                    'team_season_kit_type': snapshot_team_season_kit_type(suggestion),
                    'source_kit_type': snapshot_kit_type(source_kit_type),
                },
            )

        return Response({
            'id': suggestion.id,
            'status': suggestion.status,
            'kit_type_status': source_kit_type.status,
            'moderation_action_id': action.id,
        })


class AdminTeamSeasonKitTypeRejectAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def post(self, request, pk):
        with transaction.atomic():
            suggestion = get_object_or_404(
                TeamSeasonKitType.objects.select_for_update().select_related('kit_type'),
                pk=pk,
            )
            source_kit_type = KitType.objects.select_for_update().get(pk=suggestion.kit_type_id)
            previous_state = {
                'team_season_kit_type': snapshot_team_season_kit_type(suggestion),
                'source_kit_type': snapshot_kit_type(source_kit_type),
            }

            suggestion.status = TeamSeasonKitType.STATUS_REJECTED
            suggestion.approved_by = None
            suggestion.approved_at = None
            suggestion.save(update_fields=['status', 'approved_by', 'approved_at'])

            action = build_moderation_action_record(
                actor=request.user,
                action_type=KitTypeModerationAction.ACTION_REJECT,
                suggestion=suggestion,
                source_kit_type=source_kit_type,
                previous_state=previous_state,
                resulting_state={
                    'team_season_kit_type': snapshot_team_season_kit_type(suggestion),
                    'source_kit_type': snapshot_kit_type(source_kit_type),
                },
            )

        return Response({
            'id': suggestion.id,
            'status': suggestion.status,
            'moderation_action_id': action.id,
        })


class AdminTeamSeasonKitTypeMergeAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def post(self, request, pk):
        serializer = AdminKitTypeMergeSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        target_kit_type = serializer.context['target_kit_type']
        suggestion = get_object_or_404(
            TeamSeasonKitType.objects.select_related('kit_type'),
            pk=pk,
        )
        source_kit_type = suggestion.kit_type

        if source_kit_type.id == target_kit_type.id:
            raise ValidationError({'target_kit_type_id': 'Source and target shirt type must differ.'})

        now = timezone.now()
        affected_team_season_rows = 0
        deleted_team_season_rows = 0

        with transaction.atomic():
            suggestion = TeamSeasonKitType.objects.select_for_update().select_related('kit_type', 'team').get(pk=suggestion.pk)
            source_kit_type = KitType.objects.select_for_update().get(pk=source_kit_type.pk)
            target_kit_type = KitType.objects.select_for_update().get(pk=target_kit_type.pk)
            previous_state = {
                'team_season_kit_type': snapshot_team_season_kit_type(suggestion),
                'source_kit_type': snapshot_kit_type(source_kit_type),
                'target_kit_type': snapshot_kit_type(target_kit_type),
            }
            Kit.objects.filter(kit_type_ref=source_kit_type).update(
                kit_type_ref=target_kit_type,
                kit_type=target_kit_type.name,
            )

            team_season_rows = list(
                TeamSeasonKitType.objects.filter(kit_type=source_kit_type)
                .select_related('team', 'kit_type')
                .order_by('id')
            )
            for row in team_season_rows:
                force_approve = row.id == suggestion.id
                duplicate = TeamSeasonKitType.objects.filter(
                    team=row.team,
                    season=row.season,
                    kit_type=target_kit_type,
                ).exclude(pk=row.pk).first()

                if duplicate is not None:
                    duplicate_updates = []
                    if force_approve or row.status == TeamSeasonKitType.STATUS_APPROVED:
                        if duplicate.status != TeamSeasonKitType.STATUS_APPROVED:
                            duplicate.status = TeamSeasonKitType.STATUS_APPROVED
                            duplicate_updates.append('status')
                        duplicate.approved_by = request.user
                        duplicate.approved_at = now
                        duplicate_updates.extend(['approved_by', 'approved_at'])
                    if duplicate_updates:
                        duplicate.save(update_fields=list(dict.fromkeys(duplicate_updates)))
                    row.delete()
                    deleted_team_season_rows += 1
                    continue

                row.kit_type = target_kit_type
                if force_approve:
                    row.status = TeamSeasonKitType.STATUS_APPROVED
                    row.approved_by = request.user
                    row.approved_at = now
                    row.save(update_fields=['kit_type', 'status', 'approved_by', 'approved_at'])
                else:
                    row.save(update_fields=['kit_type'])
                affected_team_season_rows += 1

            alias_defaults = {
                'display_alias': source_kit_type.name,
                'kit_type': target_kit_type,
                'created_by': source_kit_type.created_by or request.user,
                'approved_by': request.user,
            }
            alias, created = KitTypeAlias.objects.get_or_create(
                alias_normalized=normalize_catalog_name(source_kit_type.name),
                defaults=alias_defaults,
            )
            if not created and alias.kit_type_id != target_kit_type.id:
                alias.kit_type = target_kit_type
                alias.display_alias = alias.display_alias or source_kit_type.name
                alias.approved_by = request.user
                alias.save(update_fields=['kit_type', 'display_alias', 'approved_by'])

            source_kit_type.status = KitType.STATUS_MERGED
            source_kit_type.merged_into = target_kit_type
            source_kit_type.approved_by = request.user
            source_kit_type.approved_at = now
            source_kit_type.save(
                update_fields=['status', 'merged_into', 'approved_by', 'approved_at']
            )

            action = build_moderation_action_record(
                actor=request.user,
                action_type=KitTypeModerationAction.ACTION_MERGE,
                suggestion=None,
                source_kit_type=source_kit_type,
                target_kit_type=target_kit_type,
                team_name=suggestion.team.name,
                season=suggestion.season,
                previous_state=previous_state,
                resulting_state={
                    'source_kit_type': snapshot_kit_type(source_kit_type),
                    'target_kit_type': snapshot_kit_type(target_kit_type),
                },
                is_reversible=False,
                undo_block_reason=MERGE_UNDO_BLOCK_REASON,
            )

        return Response({
            'merged_kit_type_id': source_kit_type.id,
            'target_kit_type_id': target_kit_type.id,
            'team_season_rows_updated': affected_team_season_rows,
            'team_season_rows_deleted': deleted_team_season_rows,
            'moderation_action_id': action.id,
        })


class AdminKitTypeModerationActionsAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 50

    def get(self, request):
        raw_limit = request.query_params.get('limit', self.DEFAULT_LIMIT)
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT

        limit = max(1, min(limit, self.MAX_LIMIT))
        queryset = KitTypeModerationAction.objects.select_related(
            'actor',
            'undone_by',
            'team_season_kit_type__team',
            'source_kit_type',
            'target_kit_type',
        )[:limit]
        serializer = KitTypeModerationActionSerializer(
            queryset,
            many=True,
            context={
                'request': request,
                'can_undo_moderation_action': can_undo_moderation_action,
                'moderation_action_is_currently_undoable': moderation_action_is_currently_undoable,
            },
        )
        return Response(serializer.data)


class AdminKitTypeModerationActionUndoAPI(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrModerator]

    def post(self, request, pk):
        with transaction.atomic():
            action = get_object_or_404(
                KitTypeModerationAction.objects.select_for_update(),
                pk=pk,
            )
            if not can_undo_moderation_action(request.user, action):
                return Response(status=status.HTTP_403_FORBIDDEN)

            can_undo, reason = moderation_action_is_currently_undoable(action)
            if not can_undo:
                return moderation_action_conflict_response()

            try:
                suggestion = TeamSeasonKitType.objects.select_for_update().get(pk=action.team_season_kit_type_id)
                source_kit_type = KitType.objects.select_for_update().get(pk=action.source_kit_type_id)
            except (TeamSeasonKitType.DoesNotExist, KitType.DoesNotExist):
                return moderation_action_conflict_response()

            expected_suggestion = action.resulting_state.get('team_season_kit_type')
            expected_source_type = action.resulting_state.get('source_kit_type')
            if expected_suggestion and snapshot_team_season_kit_type(suggestion) != expected_suggestion:
                return moderation_action_conflict_response()
            if expected_source_type and snapshot_kit_type(source_kit_type) != expected_source_type:
                return moderation_action_conflict_response()

            previous_suggestion = action.previous_state.get('team_season_kit_type')
            previous_source_type = action.previous_state.get('source_kit_type')
            if previous_suggestion:
                apply_team_season_kit_type_snapshot(suggestion, previous_suggestion)
            if previous_source_type:
                apply_kit_type_snapshot(source_kit_type, previous_source_type)

            action.undone_at = timezone.now()
            action.undone_by = request.user
            action.save(update_fields=['undone_at', 'undone_by'])

        return Response({
            'id': action.id,
            'undone_at': action.undone_at,
            'undone_by_username': request.user.username,
        })

# Endpoint: User collection statistics
class UserCollectionStatsAPI(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, username):
        # Get user if exists or return 404
        user = get_object_or_404(User, username=username)

        # Calculate stats
        total_value, total_kits = calculate_collection_total_value(user)

        # 3Assign calculated data to the user object
        user.total_value = total_value
        user.total_kits = total_kits

        # Calculate followers and following counts
        user.followers_count = user.followers.count()
        user.following_count = user.following.count()

        # Check if the logged-in user is following this user (if authenticated)
        user.is_followed_by_me = False
        if request.user.is_authenticated:
            user.is_followed_by_me = Follow.objects.filter(
                follower=request.user, 
                following=user
            ).exists()

        # Pass the user to the new serializer
        serializer = UserStatsProfileSerializer(user, context={'request': request})

        return Response(serializer.data)

# Endpoint: User search
class UserSearchAPI(generics.ListAPIView):
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if len(query) < 3:
            return User.objects.none() # Don't search for very short queries

        return User.objects.filter(
            username__icontains=query # Search for username fragment (case-insensitive)
        ).annotate(
            kits_count=Count('collection') # Count kits for each user
        ).order_by('-kits_count')[:10] # Limit to top 10 results


class MyCollectionValueHistoryAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not getattr(request.user.profile, 'is_pro', False):
            raise PermissionDenied('Collection value history is available for Pro members only.')

        if not request.user.collection_value_snapshots.exists():
            record_collection_value_snapshot(
                request.user,
                CollectionValueSnapshot.REASON_INITIAL,
            )

        snapshots = request.user.collection_value_snapshots.order_by('created_at', 'id')
        serializer = CollectionValueSnapshotSerializer(snapshots, many=True)
        return Response({'results': serializer.data})


class WishlistListMixin:
    serializer_class = WishlistItemSerializer
    pagination_class = None

    def get_serializer_context(self):
        context = super().get_serializer_context()
        preview_map = getattr(self, '_wishlist_preview_map', None)
        if preview_map is not None:
            context['wishlist_preview_map'] = preview_map
        return context

    def list(self, request, *args, **kwargs):
        queryset = list(self.get_queryset())
        self._wishlist_preview_map = build_wishlist_preview_map(queryset, request)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MyWishlistAPI(WishlistListMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user).select_related(
            'team', 'user', 'source_userkit', 'kit_type_ref'
        )


class UserWishlistAPI(WishlistListMixin, generics.ListAPIView):
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return WishlistItem.objects.filter(
            user__username=self.kwargs['username']
        ).select_related('team', 'user', 'source_userkit', 'kit_type_ref')


class WishlistDetailAPI(generics.DestroyAPIView):
    serializer_class = WishlistItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user).select_related(
            'team', 'user', 'source_userkit', 'kit_type_ref'
        )


class WishlistToggleAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WishlistToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        team = Team.objects.get(pk=serializer.validated_data['team_id'])
        season = serializer.validated_data['season']
        kit_type = serializer.validated_data['kit_type']
        source_userkit = serializer.validated_data.get('source_userkit')

        existing_item = WishlistItem.objects.filter(
            user=request.user,
            team=team,
            season=season,
            kit_type=kit_type,
        ).first()

        if existing_item is not None:
            existing_item.delete()
            return Response({
                'is_wishlisted': False,
                'item': None,
            }, status=status.HTTP_200_OK)

        wishlist_limit = get_wishlist_limit(request.user)
        current_count = WishlistItem.objects.filter(user=request.user).count()
        if wishlist_limit is not None and current_count >= wishlist_limit:
            return Response({
                'detail': 'Wishlist limit reached.',
                'code': 'wishlist_limit_reached',
                'limit': wishlist_limit,
            }, status=status.HTTP_400_BAD_REQUEST)

        wishlist_item = WishlistItem.objects.create(
            user=request.user,
            team=team,
            season=season,
            kit_type=kit_type,
            source_userkit=source_userkit,
        )
        preview_map = build_wishlist_preview_map([wishlist_item], request)
        response_serializer = WishlistItemSerializer(
            wishlist_item,
            context={
                'request': request,
                'wishlist_preview_map': preview_map,
            },
        )
        return Response({
            'is_wishlisted': True,
            'item': response_serializer.data,
        }, status=status.HTTP_200_OK)


class KitSearchSuggestionsAPI(generics.ListAPIView):
    serializer_class = KitSearchSuggestionSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 50
    MIN_QUERY_LENGTH = 2

    def get_limit_value(self):
        limit = self.request.query_params.get('limit', self.DEFAULT_LIMIT)

        try:
            limit_value = int(limit)
        except (TypeError, ValueError):
            limit_value = self.DEFAULT_LIMIT

        return max(1, min(limit_value, self.MAX_LIMIT))

    def get_matching_teams(self, parsed_query):
        team_text = parsed_query['team_text']
        if not team_text:
            return []

        return list(
            Team.objects.filter(
                is_verified=True,
                name__icontains=team_text,
            )
        )

    def get_matching_seasons(self, parsed_query):
        generated_seasons = get_generated_seasons()

        if parsed_query['exact_season']:
            return [
                season for season in generated_seasons
                if season_matches_exact(season, parsed_query['exact_season'])
            ]

        if parsed_query['season_prefix']:
            return [
                season for season in generated_seasons
                if season_matches_prefix(season, parsed_query['season_prefix'])
            ]

        if parsed_query['year_fragment']:
            return [
                season for season in generated_seasons
                if season_matches_year_fragment(season, parsed_query['year_fragment'])
            ]

        return generated_seasons

    def get_matching_kit_types(self, parsed_query):
        if parsed_query['kit_types']:
            return parsed_query['kit_types']
        return SUPPORTED_KIT_TYPES

    def get_preview_map(self, suggestions):
        if not suggestions:
            return {}

        team_ids = {suggestion['team_id'] for suggestion in suggestions}
        seasons = {suggestion['season'] for suggestion in suggestions}
        suggested_types = {suggestion['kit_type'] for suggestion in suggestions}

        type_filter = Q()
        for suggested_type in suggested_types:
            type_filter |= get_upload_preview_type_filter(suggested_type)

        preview_images = UserKitImage.objects.filter(
            user_kit__kit__team_id__in=team_ids,
            user_kit__kit__season__in=seasons,
        ).filter(
            type_filter
        ).select_related(
            'user_kit__kit',
            'user_kit__kit__team',
        ).order_by(
            'user_kit__kit__team_id',
            'user_kit__kit__season',
            'user_kit__kit__kit_type',
            'order',
            'created_at',
            'id',
        )

        preview_map = {}
        for preview_image in preview_images:
            preview_key = (
                preview_image.user_kit.kit.team_id,
                preview_image.user_kit.kit.season,
                normalize_stored_kit_type(preview_image.user_kit.kit.kit_type),
            )
            if preview_key in preview_map:
                continue

            preview_url = preview_image.image.url
            if self.request is not None:
                preview_url = self.request.build_absolute_uri(preview_url)

            preview_map[preview_key] = preview_url

        return preview_map

    def get_queryset(self):
        parsed_query = parse_kit_search_query(self.request.query_params.get('q', ''))
        normalized_query = parsed_query['normalized_query']

        if len(normalized_query) < self.MIN_QUERY_LENGTH:
            return []

        matching_teams = self.get_matching_teams(parsed_query)
        if not matching_teams:
            return []

        matching_seasons = self.get_matching_seasons(parsed_query)
        if not matching_seasons:
            return []

        matching_kit_types = self.get_matching_kit_types(parsed_query)

        suggestions = [
            get_generated_suggestion(team, season, kit_type)
            for team in matching_teams
            for season in matching_seasons
            for kit_type in matching_kit_types
        ]

        ranked_suggestions = sorted(
            suggestions,
            key=lambda suggestion: (
                get_team_match_rank(suggestion['team_name'], parsed_query['team_text']),
                get_generated_season_match_rank(suggestion['season'], parsed_query),
                -get_season_sort_year(suggestion['season']),
                get_kit_type_order(suggestion['kit_type']),
                suggestion['team_name'].lower(),
            ),
        )

        limited_suggestions = ranked_suggestions[:self.get_limit_value()]
        preview_map = self.get_preview_map(limited_suggestions)

        for suggestion in limited_suggestions:
            preview_key = (
                suggestion['team_id'],
                suggestion['season'],
                suggestion['kit_type'],
            )
            preview_image = preview_map.get(preview_key)
            suggestion['preview_image'] = preview_image
            suggestion['has_uploads'] = preview_image is not None

        return limited_suggestions


class ConversationListAPI(generics.ListAPIView):
    serializer_class = ConversationListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_user_conversations_queryset(self.request.user)


class StartConversationAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ConversationStartSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        recipient = serializer.validated_data['recipient']
        conversation = Conversation.get_or_create_between(request.user, recipient)
        response_serializer = ConversationDetailSerializer(conversation, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ConversationDetailAPI(generics.RetrieveAPIView):
    serializer_class = ConversationDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'conversation_id'

    def get_queryset(self):
        return get_user_conversations_queryset(self.request.user)


class ConversationMessagesAPI(APIView):
    permission_classes = [IsAuthenticated]
    DEFAULT_LIMIT = 30
    MAX_LIMIT = 100

    def _get_user_conversation(self, request, conversation_id):
        queryset = Conversation.objects.select_related(
            'participant_one',
            'participant_one__profile',
            'participant_two',
            'participant_two__profile',
        ).filter(
            Q(participant_one=request.user) | Q(participant_two=request.user)
        )
        return get_object_or_404(queryset, pk=conversation_id)

    def _get_limit(self, request):
        raw_limit = request.query_params.get('limit')
        if raw_limit is None:
            return self.DEFAULT_LIMIT

        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return self.DEFAULT_LIMIT

        if limit <= 0:
            return self.DEFAULT_LIMIT

        return min(limit, self.MAX_LIMIT)

    def get(self, request, conversation_id):
        conversation = self._get_user_conversation(request, conversation_id)
        conversation.messages.filter(
            read_at__isnull=True
        ).exclude(
            sender=request.user
        ).update(
            read_at=timezone.now()
        )

        limit = self._get_limit(request)
        before = request.query_params.get('before')
        messages_queryset = conversation.messages.select_related('sender')

        if before is not None:
            try:
                before_id = int(before)
            except (TypeError, ValueError):
                return Response(
                    {'before': ['before must be a valid message id.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            anchor_message = Message.objects.filter(pk=before_id).first()
            if anchor_message is None:
                return Response(
                    {'before': ['Message not found.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if anchor_message.conversation_id != conversation.id:
                return Response(
                    {'before': ['Message does not belong to this conversation.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            messages_queryset = messages_queryset.filter(id__lt=before_id)

        messages_desc = list(
            messages_queryset.order_by('-created_at', '-id')[:limit]
        )
        messages = list(reversed(messages_desc))

        if messages:
            first_message = messages[0]
            has_more = messages_queryset.filter(
                Q(created_at__lt=first_message.created_at) |
                Q(created_at=first_message.created_at, id__lt=first_message.id)
            ).exists()
        else:
            has_more = False

        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response({
            'results': serializer.data,
            'has_more': has_more,
        })

    def post(self, request, conversation_id):
        conversation = self._get_user_conversation(request, conversation_id)
        serializer = MessageWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.save(conversation=conversation, sender=request.user)
        response_serializer = MessageSerializer(message, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class UnreadMessagesCountAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_count = Message.objects.filter(
            read_at__isnull=True,
        ).exclude(
            sender=request.user,
        ).filter(
            Q(conversation__participant_one=request.user) |
            Q(conversation__participant_two=request.user)
        ).count()

        return Response({'unread_count': unread_count})


class NotificationListAPI(APIView):
    permission_classes = [IsAuthenticated]
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 50

    def _get_limit(self, request):
        raw_limit = request.query_params.get('limit')
        if raw_limit is None:
            return self.DEFAULT_LIMIT

        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return self.DEFAULT_LIMIT

        if limit <= 0:
            return self.DEFAULT_LIMIT

        return min(limit, self.MAX_LIMIT)

    def get(self, request):
        queryset = get_user_notifications_queryset(request.user)
        limit = self._get_limit(request)
        before = request.query_params.get('before')

        if before is not None:
            try:
                before_id = int(before)
            except (TypeError, ValueError):
                return Response(
                    {'before': ['before must be a valid notification id.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            anchor_notification = queryset.filter(pk=before_id).first()
            if anchor_notification is None:
                return Response(
                    {'before': ['Notification not found.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = queryset.filter(
                Q(created_at__lt=anchor_notification.created_at) |
                Q(created_at=anchor_notification.created_at, id__lt=anchor_notification.id)
            )

        notifications = list(queryset[:limit])

        if notifications:
            oldest_notification = notifications[-1]
            has_more = queryset.filter(
                Q(created_at__lt=oldest_notification.created_at) |
                Q(created_at=oldest_notification.created_at, id__lt=oldest_notification.id)
            ).exists()
        else:
            has_more = False

        serializer = NotificationSerializer(notifications, many=True, context={'request': request})
        return Response({
            'results': serializer.data,
            'has_more': has_more,
        })


class NotificationUnreadCountAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_count = Notification.objects.filter(
            recipient=request.user,
            read_at__isnull=True,
        ).count()
        return Response({'unread_count': unread_count})


class MarkNotificationsReadAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user,
            read_at__isnull=True,
        ).update(read_at=timezone.now())

        return Response({
            'marked_read_count': updated,
            'unread_count': 0,
        })

# Endpoint: Update user profile
class UpdateProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        # Return the profile of the currently authenticated user
        return self.request.user.profile

# Endpoint: Like/unlike a kit in user's collection
class ToggleLikeAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        kit = get_object_or_404(UserKit, pk=pk)
        user = request.user

        liked = False
        if kit.likes.filter(id=user.id).exists():
            kit.likes.remove(user)
            liked = False
            Notification.objects.filter(
                recipient=kit.user,
                actor=user,
                type='kit_like',
                kit=kit,
            ).delete()
        else:
            kit.likes.add(user)
            liked = True
            if kit.user_id != user.id:
                Notification.objects.get_or_create(
                    recipient=kit.user,
                    actor=user,
                    type='kit_like',
                    kit=kit,
                )
        
        return Response({
            "liked": liked,
            "likes_count": kit.likes.count()
        }, status=status.HTTP_200_OK)


class KitCommentsAPI(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, userkit_id):
        kit = get_object_or_404(UserKit, pk=userkit_id)
        comments = get_top_level_comments_queryset(request.user).filter(kit=kit)
        serializer = KitCommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, userkit_id):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        kit = get_object_or_404(UserKit, pk=userkit_id)
        serializer = KitCommentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = serializer.save(kit=kit, user=request.user)
        if kit.user_id != request.user.id:
            Notification.objects.get_or_create(
                recipient=kit.user,
                actor=request.user,
                type='kit_comment',
                kit=kit,
                comment=comment,
            )
        response_serializer = KitCommentSerializer(comment, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ReplyToCommentAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, comment_id):
        target_comment = get_object_or_404(KitComment, pk=comment_id)
        thread_parent = target_comment.parent if target_comment.parent_id is not None else target_comment

        serializer = KitCommentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reply = serializer.save(
            kit=target_comment.kit,
            user=request.user,
            parent=thread_parent,
            reply_to=target_comment,
        )
        if target_comment.user_id != request.user.id:
            Notification.objects.get_or_create(
                recipient=target_comment.user,
                actor=request.user,
                type='comment_reply',
                kit=target_comment.kit,
                comment=reply,
            )
        response_serializer = KitCommentSerializer(reply, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ToggleCommentLikeAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, comment_id):
        comment = get_object_or_404(KitComment, pk=comment_id)
        like = KitCommentLike.objects.filter(comment=comment, user=request.user).first()

        liked = False
        if like:
            like.delete()
            Notification.objects.filter(
                recipient=comment.user,
                actor=request.user,
                type='comment_like',
                kit=comment.kit,
                comment=comment,
            ).delete()
        else:
            KitCommentLike.objects.create(comment=comment, user=request.user)
            liked = True
            if comment.user_id != request.user.id:
                Notification.objects.get_or_create(
                    recipient=comment.user,
                    actor=request.user,
                    type='comment_like',
                    kit=comment.kit,
                    comment=comment,
                )

        return Response(
            {
                'liked': liked,
                'likes_count': comment.comment_likes.count(),
            },
            status=status.HTTP_200_OK,
        )


class DeleteCommentAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, comment_id):
        comment = get_object_or_404(KitComment, pk=comment_id)
        can_delete = comment.user_id == request.user.id or is_staff_or_moderator(request.user)

        if not can_delete:
            return Response(
                {'detail': 'You do not have permission to delete this comment.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportKitAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, userkit_id):
        kit = get_object_or_404(UserKit, pk=userkit_id)

        if KitReport.objects.filter(kit=kit, reporter=request.user).exists():
            return Response(
                {'detail': 'You have already reported this kit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = KitReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(kit=kit, reporter=request.user)

        return Response(
            {'message': 'Report submitted successfully.'},
            status=status.HTTP_201_CREATED,
        )

# Endpoint: List of leagues
class LeagueListAPI(generics.ListAPIView):
    queryset = League.objects.all().select_related('country').order_by('order', 'name')
    serializer_class = LeagueSerializer
    permission_classes = [permissions.AllowAny]

# Endpoint: Teams by League
class TeamsByLeagueAPI(generics.ListAPIView):
    serializer_class = TeamSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        league_id = self.kwargs['league_id']
        return Team.objects.filter(league_id=league_id).select_related('country', 'league').order_by('name')

# Endpoint: Top liked kits for a specific team
class TopKitsByTeamAPI(generics.ListAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        team_id = self.kwargs['team_id']
        
        return UserKit.objects.filter(kit__team_id=team_id)\
            .select_related('kit', 'kit__team', 'kit__kit_type_ref', 'shirt_version', 'user')\
            .prefetch_related('images', 'likes')\
            .annotate(likes_count=Count('likes', distinct=True), comments_count=Count('comments', distinct=True))\
            .order_by('-likes_count', '-added_at')


class ApprovedTeamSeasonKitTypesAPI(generics.ListAPIView):
    serializer_class = ApprovedTeamSeasonKitTypeSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        return (
            TeamSeasonKitType.objects.filter(
                team_id=self.kwargs['team_id'],
                status=TeamSeasonKitType.STATUS_APPROVED,
                kit_type__status=KitType.STATUS_APPROVED,
            )
            .select_related('team', 'kit_type')
            .order_by('-season', 'kit_type__sort_order', 'kit_type__name', 'id')
        )

# Endpoint: Check username availability
class CheckUsernameAPI(APIView):
    def get(self, request):
        username = request.query_params.get('q', '').strip()
        if not username:
            return Response({"available": False, "error": "Empty username"})
        
        # Check if username exists excluding the current user
        exists = User.objects.filter(username__iexact=username).exclude(id=request.user.id).exists()
        return Response({"available": not exists})

# Endpoint: List of countries
class CountryListView(generics.ListAPIView):
    queryset = Country.objects.all().order_by('name')
    serializer_class = CountrySerializer
    
    # Allow everyone to access this endpoint
    permission_classes = [permissions.AllowAny] 
    
    pagination_class = None

# Endpoint: Toggle follow/unfollow another user
class ToggleFollowView(APIView):
    # Only authenticated users can follow/unfollow
    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        # Find the user to follow or return 404 if not found
        user_to_follow = get_object_or_404(User, username=username)

        # Prevent users from following themselves
        if request.user == user_to_follow:
            return Response({"error": "You cannot follow yourself."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the follow relationship already exists
        follow_instance = Follow.objects.filter(
            follower=request.user, 
            following=user_to_follow
        ).first()

        if follow_instance:
            # If it exists -> Delete it (Unfollow)
            follow_instance.delete()
            return Response({"is_following": False}, status=status.HTTP_200_OK)
        else:
            # If it doesn't exist -> Create it (Follow)
            Follow.objects.create(follower=request.user, following=user_to_follow)
            Notification.objects.get_or_create(
                recipient=user_to_follow,
                actor=request.user,
                type='follow',
                kit=None,
            )
            return Response({"is_following": True}, status=status.HTTP_201_CREATED)

# Endpoint: List of kit variants for a specific team with optional filters (season, type)
class KitVariantsAPI(generics.ListAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardResultsSetPagination # paginate results

    def get_queryset(self):
        team_identifier = self.kwargs.get('team_identifier')
        season = self.request.query_params.get('season')
        kit_type = self.request.query_params.get('type')
        team = get_team_by_identifier(team_identifier)
        if team is None:
            return UserKit.objects.none()

        queryset = UserKit.objects.filter(kit__team=team)

        if season:
            queryset = queryset.filter(kit__season=season)
        if kit_type:
            queryset = queryset.filter(get_history_type_filter(kit_type))

        return queryset\
            .select_related('kit', 'kit__team', 'kit__kit_type_ref', 'shirt_version', 'user')\
            .prefetch_related('images', 'likes')\
            .annotate(likes_count=Count('likes', distinct=True), comments_count=Count('comments', distinct=True))\
            .order_by('-likes_count', '-added_at')

# Endpoint: List of followers for a user
class FollowersListAPI(generics.ListAPIView):
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        # Find the user whose followers we want to list, or return 404 if not found
        user = get_object_or_404(User, username=self.kwargs['username'])
        
        # Get IDs of users who are following this user
        follower_ids = Follow.objects.filter(following=user).values_list('follower_id', flat=True)
        
        # Return the list of those users, annotating with their kit count
        return User.objects.filter(id__in=follower_ids).annotate(
            followers_count=Count('followers', distinct=True)
        ).order_by('-followers_count')

# Endpoint: List of users that a user is following
class FollowingListAPI(generics.ListAPIView):
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        # Find the user whose followings we want to list, or return 404 if not found
        user = get_object_or_404(User, username=self.kwargs['username'])
        
        # Get IDs of users that this user is following
        following_ids = Follow.objects.filter(follower=user).values_list('following_id', flat=True)
        
        # Return the list of those users
        return User.objects.filter(id__in=following_ids).annotate(
            followers_count=Count('followers', distinct=True)
        ).order_by('-followers_count')

# Endpoint: List of users that liked a specific kit
class KitLikersListAPI(generics.ListAPIView):
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        kit_id = self.kwargs['kit_id']

        # Get IDs of users who liked this kit
        liker_ids = UserKit.objects.filter(id=kit_id).values_list('likes__id', flat=True)

        # Return the list of those users, annotating with their kit count
        return User.objects.filter(id__in=liker_ids).annotate(
            followers_count=Count('followers', distinct=True)
        ).order_by('-followers_count')
