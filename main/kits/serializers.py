from rest_framework import serializers
from .models import Team, Kit, UserKit, UserKitImage, User
from django.contrib.auth.models import User
from dj_rest_auth.serializers import UserDetailsSerializer

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
    # Read-only nested serializers
    kit = KitSerializer(read_only=True)
    images = UserKitImageSerializer(many=True, read_only=True)

    size_display = serializers.CharField(source='get_size_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    technology_display = serializers.CharField(source='get_shirt_technology_display', read_only=True)

    # Write-only fields for creating/updating UserKit
    team_name = serializers.CharField(write_only=True)
    season = serializers.CharField(write_only=True)
    kit_type = serializers.CharField(write_only=True)

    class Meta:
        model = UserKit
        fields = [
            'id', 'user', 
            # Read-only fields
            'kit', 'images', 'condition_display', 'technology_display', 'final_value', 'size_display',
            # Write-only fields
            'team_name', 'season', 'kit_type',
            # Modifiable fields
            'condition', 'shirt_technology', 'size', 'for_sale', 'manual_value'
        ]
        read_only_fields = ['user', 'final_value', 'kit']
    
    # Override create method to handle nested kit creation
    def create(self, validated_data):
        team_name = validated_data.pop('team_name')
        season = validated_data.pop('season')
        kit_type = validated_data.pop('kit_type')

        # Get or create the Team
        team, _ = Team.objects.get_or_create(name=team_name.title())

        # Get or create the Kit
        kit, _ = Kit.objects.get_or_create(team=team, season=season, kit_type=kit_type, defaults={'estimated_price': 0})

        # Create the UserKit
        user_kit = UserKit.objects.create(kit=kit, **validated_data)

        # Images handling
        request = self.context.get('request')
        if request and request.FILES:
            images_list = request.FILES.getlist('images')
            if images_list:
                for image_data in images_list:
                    UserKitImage.objects.create(user_kit=user_kit, image=image_data)

        return user_kit

# User serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_pro', 'is_moderator']
        read_only_fields = ['is_pro', 'is_moderator']

# Custom User Details Serializer to include is_pro field
class CustomUserDetailsSerializer(UserDetailsSerializer):

    is_pro = serializers.SerializerMethodField()

    class Meta(UserDetailsSerializer.Meta):
        fields = UserDetailsSerializer.Meta.fields + ('is_pro',) 

    def get_is_pro(self, obj):
        # Safely get is_pro from profile
        try:
            return obj.profile.is_pro
        except AttributeError:
            return False