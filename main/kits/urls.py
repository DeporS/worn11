from django.urls import path
from .views import (
    MyCollectionAPI, 
    MyCollectionDetailAPI,
    UserCollectionAPI, 
    KitCatalogAPI, 
    KitOptionsView,
    TeamSearchAPI,
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
]