from rest_framework import generics, permissions
from rest_framework.permissions import IsAuthenticated
from .models import UserKit, Kit, SIZE_CHOICES, CONDITION_CHOICES, SHIRT_TECHNOLOGIES, SHIRT_TYPES, Team
from .serializers import UserKitSerializer, KitSerializer, TeamSerializer
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count

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
        return UserKit.objects.filter(user=self.request.user)

# Endpoint: Show other user's collection
class UserCollectionAPI(generics.ListAPIView):
    serializer_class = UserKitSerializer
    permission_classes = [permissions.AllowAny] # Publicly accessible

    def get_queryset(self):
        # Get username from URL
        username = self.kwargs['username']

        # Return kits of the specified user
        return UserKit.objects.filter(user__username=username).select_related('kit', 'kit__team').order_by('-added_at')

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

# Endpoint: User's collection statistics
class UserCollectionStatsAPI(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, username):
        queryset = UserKit.objects.filter(user__username=username)

        stats = queryset.aggregate(
            total_value=Sum('final_value'), # Total collection value
            total_kits=Count('id')  # Shirt count
        )

        return Response({
            "total_value": stats['total_value'] or 0,
            "total_kits": stats['total_kits'] or 0
        })