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

from .models import League, UserKit, Kit, SIZE_CHOICES, CONDITION_CHOICES, SHIRT_TECHNOLOGIES, SHIRT_TYPES, Team, Profile, Country, Follow, KitComment, KitCommentLike, KitReport, Conversation, Message
from .serializers import LeagueSerializer, UserKitSerializer, KitSerializer, TeamSerializer, UserSearchSerializer, ProfileSerializer, UserSerializer, UserStatsProfileSerializer, CountrySerializer, KitCommentSerializer, KitCommentWriteSerializer, KitReportSerializer, ConversationListSerializer, ConversationDetailSerializer, ConversationStartSerializer, MessageSerializer, MessageWriteSerializer


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
            queryset = queryset.filter(kit__kit_type=kit_type)

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
