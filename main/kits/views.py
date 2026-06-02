from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from rest_framework.throttling import ScopedRateThrottle
from .throttles import KitCreationThrottle

from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Exists, OuterRef, Value, BooleanField, Prefetch, Q, Subquery
from django.contrib.auth.models import User
from django.utils import timezone
from urllib.parse import urlencode
import re

from .models import League, UserKit, Kit, SIZE_CHOICES, CONDITION_CHOICES, SHIRT_TECHNOLOGIES, SHIRT_TYPES, Team, Profile, Country, Follow, KitComment, KitCommentLike, KitReport, Conversation, Message
from .serializers import LeagueSerializer, UserKitSerializer, KitSerializer, TeamSerializer, UserSearchSerializer, ProfileSerializer, UserSerializer, UserStatsProfileSerializer, CountrySerializer, KitCommentSerializer, KitCommentWriteSerializer, KitReportSerializer, ConversationListSerializer, ConversationDetailSerializer, ConversationStartSerializer, MessageSerializer, MessageWriteSerializer, KitSearchSuggestionSerializer


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
    query_string = urlencode({
        'season': season,
        'type': kit_type,
    })
    return {
        'team_id': team.id,
        'team_name': team.name,
        'season': season,
        'kit_type': kit_type,
        'label': f"{team.name} {season} {kit_type}",
        'url': f"/history/team/{team.id}/variants?{query_string}",
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


def get_public_user_kits_queryset():
    return UserKit.objects.filter(
        in_the_collection=True,
    ).select_related(
        'kit',
        'kit__team',
        'user',
    ).prefetch_related(
        'images',
        'likes',
    ).annotate(
        likes_count=Count('likes', distinct=True),
        comments_count=Count('comments', distinct=True),
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
            .select_related('kit', 'kit__team')\
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
        serializer.save(user=self.request.user)

# Endpoint: Detail, update, delete for a specific kit in collection
class MyCollectionDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserKit.objects.filter(user=self.request.user)\
            .select_related('kit', 'kit__team')\
            .prefetch_related('images')\
            .annotate(likes_count=Count('likes', distinct=True), comments_count=Count('comments', distinct=True))\
            .order_by('-added_at')

# Endpoint: Show other user's collection
class UserCollectionAPI(generics.ListAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [permissions.AllowAny] # Publicly accessible

    def get_queryset(self):
        # Get username from URL
        username = self.kwargs['username']

        # Return kits of the specified user
        return UserKit.objects.filter(user__username=username)\
            .select_related('kit', 'kit__team')\
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

# Endpoint: Catalog of all available kits (e.g., for selection when adding)
class KitCatalogAPI(generics.ListAPIView):
    queryset = Kit.objects.all()
    serializer_class = KitSerializer

# Endpoint: Get options for kit attributes
class KitOptionsView(APIView):
    def get(self, request):
        return Response({
            "sizes": [{'value': key, 'label': label} for key, label in SIZE_CHOICES],
            "conditions": [{'value': key, 'label': label} for key, label in CONDITION_CHOICES],
            "technologies": [{'value': key, 'label': label} for key, label in SHIRT_TECHNOLOGIES],
            "types": [{'value': key, 'label': label} for key, label in SHIRT_TYPES],
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
        )[:5] # Limit to 5 results

# Endpoint: User collection statistics
class UserCollectionStatsAPI(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, username):
        # Get user if exists or return 404
        user = get_object_or_404(User, username=username)

        # Calculate stats
        stats = UserKit.objects.filter(
            user=user,
            in_the_collection=True
        ).aggregate(
            total_value=Sum('final_value'), # Sum the value of all kits
            total_kits=Count('id')          # Count the number of kits
        )

        # 3Assign calculated data to the user object
        user.total_value = stats['total_value'] or 0
        user.total_kits = stats['total_kits'] or 0

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

        return ranked_suggestions[:self.get_limit_value()]


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
        else:
            kit.likes.add(user)
            liked = True
        
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
        else:
            KitCommentLike.objects.create(comment=comment, user=request.user)
            liked = True

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
        profile = getattr(request.user, 'profile', None)
        can_delete = (
            comment.user_id == request.user.id
            or request.user.is_staff
            or bool(profile and profile.is_moderator)
        )

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
        return Team.objects.filter(league_id=league_id).order_by('name')

# Endpoint: Top liked kits for a specific team
class TopKitsByTeamAPI(generics.ListAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        team_id = self.kwargs['team_id']
        
        return UserKit.objects.filter(kit__team_id=team_id)\
            .select_related('kit', 'kit__team', 'user')\
            .prefetch_related('images', 'likes')\
            .annotate(likes_count=Count('likes', distinct=True), comments_count=Count('comments', distinct=True))\
            .order_by('-likes_count', '-added_at')

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
            return Response({"is_following": True}, status=status.HTTP_201_CREATED)

# Endpoint: List of kit variants for a specific team with optional filters (season, type)
class KitVariantsAPI(generics.ListAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardResultsSetPagination # paginate results

    def get_queryset(self):
        team_id = self.kwargs['team_id']
        season = self.request.query_params.get('season')
        kit_type = self.request.query_params.get('type')

        queryset = UserKit.objects.filter(kit__team_id=team_id)

        if season:
            queryset = queryset.filter(kit__season=season)
        if kit_type:
            queryset = queryset.filter(get_history_type_filter(kit_type))

        return queryset\
            .select_related('kit', 'kit__team', 'user')\
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
