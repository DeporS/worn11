from django.urls import path
from .views import MyCollectionAPI, KitCatalogAPI, UserCollectionAPI

urlpatterns = [
    path('my-collection/', MyCollectionAPI.as_view(), name='api-my-collection'),
    path('catalog/', KitCatalogAPI.as_view(), name='api-catalog'),
    path('user-collection/<str:username>/', UserCollectionAPI.as_view(), name='api-user-collection'),
]