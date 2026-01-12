from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    MyCollectionAPI, 
    MyCollectionDetailAPI,
    UserCollectionAPI, 
    KitCatalogAPI, 
    KitOptionsView,
    TeamSearchAPI,
    UserCollectionStatsAPI,
    UserSearchAPI,
    UpdateProfileView,
    CurrentUserAPI,
    ToggleLikeAPI,
)
from .views_auth import GoogleLogin


urlpatterns = [
    path('my-collection/', MyCollectionAPI.as_view(), name='api-my-collection'),
    path('my-collection/<int:pk>/', MyCollectionDetailAPI.as_view(), name='api-my-collection-detail'),
    path('catalog/', KitCatalogAPI.as_view(), name='api-catalog'),
    path('user-collection/<str:username>/', UserCollectionAPI.as_view(), name='api-user-collection'),
    path('auth/google/', GoogleLogin.as_view(), name='google_login'),
    path('options/', KitOptionsView.as_view(), name='kit-options'),
    path('teams/search/', TeamSearchAPI.as_view(), name='team-search'),
    path('user-stats/<str:username>/', UserCollectionStatsAPI.as_view(), name='user-stats'),
    path('users/search/', UserSearchAPI.as_view(), name='user-search'),
    path('profile/update/', UpdateProfileView.as_view(), name='update-profile'),
    path('auth/user/', CurrentUserAPI.as_view(), name='current-user'),
    path('kits/<int:pk>/like/', ToggleLikeAPI.as_view(), name='toggle-like'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)