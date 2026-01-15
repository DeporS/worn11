from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework.pagination import PageNumberPagination

from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count
from django.contrib.auth.models import User

from .models import League, UserKit, Kit, SIZE_CHOICES, CONDITION_CHOICES, SHIRT_TECHNOLOGIES, SHIRT_TYPES, Team, Profile
from .serializers import LeagueSerializer, UserKitSerializer, KitSerializer, TeamSerializer, UserSearchSerializer, ProfileSerializer, UserSerializer, UserStatsProfileSerializer

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

    def get_queryset(self):
        # Return only kits of the logged-in user
        return UserKit.objects.filter(user=self.request.user).select_related('kit', 'kit__team').order_by('-added_at')

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
            .annotate(likes_count=Count('likes', distinct=True))\
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
            .annotate(likes_count=Count('likes', distinct=True))\
            .order_by('-added_at')

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

    def get_queryset(self):
        # Get search query from URL parameters e.g., /api/teams/search/?q=Bar
        query = self.request.query_params.get('q', '')

        if len(query) < 2:
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
        stats = UserKit.objects.filter(user=user).aggregate(
            total_value=Sum('final_value'), # Sum the value of all kits
            total_kits=Count('id')          # Count the number of kits
        )

        # 3Assign calculated data to the user object
        user.total_value = stats['total_value'] or 0
        user.total_kits = stats['total_kits'] or 0

        # Pass the user to the new serializer
        serializer = UserStatsProfileSerializer(user, context={'request': request})

        return Response(serializer.data)

# Endpoint: User search
class UserSearchAPI(generics.ListAPIView):
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if len(query) < 2:
            return User.objects.none() # Don't search for very short queries

        return User.objects.filter(
            username__icontains=query # Search for username fragment (case-insensitive)
        ).annotate(
            kits_count=Count('collection') # Count kits for each user
        ).order_by('-kits_count')[:10] # Limit to top 10 results

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
            .annotate(likes_total=Count('likes'))\
            .order_by('-likes_total', '-added_at')