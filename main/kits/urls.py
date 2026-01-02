from django.urls import path
from .views import (
    MyCollectionAPI, 
    UserCollectionAPI, 
    KitCatalogAPI, 
    KitOptionsView
)
from .views_auth import GoogleLogin


urlpatterns = [
    path('my-collection/', MyCollectionAPI.as_view(), name='api-my-collection'),
    path('catalog/', KitCatalogAPI.as_view(), name='api-catalog'),
    path('user-collection/<str:username>/', UserCollectionAPI.as_view(), name='api-user-collection'),
    path('auth/google/', GoogleLogin.as_view(), name='google_login'),
    path('options/', KitOptionsView.as_view(), name='kit-options'),
]