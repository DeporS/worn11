from rest_framework import serializers
from .models import Team, Kit, UserKit, UserKitImage

# Team Serializer
class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name', 'logo']

# Kit Serializer
class KitSerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)

    class Meta:
        model = Kit
        fields = ['id', 'team', 'season', 'kit_type', 'estimated_price', 'main_image']

# UserKit Image Serializer
class UserKitImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserKitImage
        fields = ['id', 'image', 'created_at']

# UserKit Serializer
class UserKitSerializer(serializers.ModelSerializer):
    kit = KitSerializer(read_only=True)
    images = UserKitImageSerializer(many=True, read_only=True)

    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    technology_display = serializers.CharField(source='get_shirt_technology_display', read_only=True)

    class Meta:
        model = UserKit
        fields = [
            'id', 'user', 'kit', 'shirt_technology', 'condition', 'size',
            'for_sale', 'manual_value', 'final_value', 'images',
            'condition_display', 'technology_display'
        ]