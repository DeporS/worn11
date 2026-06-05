from rest_framework import serializers
from .models import Country, League, Team, Kit, UserKit, UserKitImage, User, Profile, KitComment, KitReport, Conversation, Message, Notification, CollectionValueSnapshot, build_team_slug
from django.contrib.auth.models import User
from dj_rest_auth.serializers import UserDetailsSerializer
import json


class CommentAuthorSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(source='profile.avatar', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'avatar']


class KitCommentSerializer(serializers.ModelSerializer):
    user = CommentAuthorSerializer(read_only=True)
    parent_id = serializers.IntegerField(source='parent.id', read_only=True)
    reply_to_id = serializers.IntegerField(source='reply_to.id', read_only=True)
    reply_to_username = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    is_liked_by_me = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = KitComment
        fields = [
            'id',
            'body',
            'created_at',
            'updated_at',
            'user',
            'parent_id',
            'reply_to_id',
            'reply_to_username',
            'likes_count',
            'is_liked_by_me',
            'reply_count',
            'can_delete',
            'replies',
        ]

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        profile = getattr(request.user, 'profile', None)
        return (
            obj.user_id == request.user.id
            or request.user.is_staff
            or bool(profile and profile.is_moderator)
        )

    def get_likes_count(self, obj):
        return getattr(obj, 'likes_count', obj.comment_likes.count())

    def get_reply_count(self, obj):
        return getattr(obj, 'reply_count', obj.replies.count())

    def get_reply_to_username(self, obj):
        if obj.parent_id is None:
            return None

        reply_to = getattr(obj, 'reply_to', None)
        if reply_to and reply_to.user_id:
            return reply_to.user.username

        parent = getattr(obj, 'parent', None)
        if parent and parent.user_id:
            return parent.user.username

        return None

    def get_is_liked_by_me(self, obj):
        annotated_value = getattr(obj, 'is_liked_by_me', None)
        if annotated_value is not None:
            return annotated_value

        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        return obj.comment_likes.filter(user=request.user).exists()

    def get_replies(self, obj):
        replies = getattr(obj, 'prefetched_replies', None)
        if replies is None:
            replies = obj.replies.none()

        serializer = KitCommentSerializer(replies, many=True, context=self.context)
        return serializer.data


class KitCommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = KitComment
        fields = ['body']

    def validate_body(self, value):
        cleaned = (value or '').strip()
        if not cleaned:
            raise serializers.ValidationError('Comment cannot be empty.')
        return cleaned


class KitReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = KitReport
        fields = ['reason', 'description']

    def validate_description(self, value):
        return (value or '').strip()

    def validate(self, attrs):
        reason = attrs.get('reason')
        description = (attrs.get('description') or '').strip()

        if reason == 'other' and not description:
            raise serializers.ValidationError({
                'description': 'Description is required when selecting Other.'
            })

        attrs['description'] = description
        return attrs


class ConversationUserSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(source='profile.avatar', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'avatar']


class ConversationStartSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    kit_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        username = attrs.get('username')
        kit_id = attrs.get('kit_id')
        request = self.context['request']
        has_username = username is not None
        has_kit_id = kit_id is not None

        if has_username == has_kit_id:
            raise serializers.ValidationError('Provide either username or kit_id.')

        if username:
            cleaned_username = username.strip()
            if not cleaned_username:
                raise serializers.ValidationError({'username': 'Username is required.'})

            recipient = User.objects.filter(username__iexact=cleaned_username).first()
            if recipient is None:
                raise serializers.ValidationError({'username': 'User not found.'})
        else:
            try:
                user_kit = UserKit.objects.select_related('user').get(pk=kit_id)
            except UserKit.DoesNotExist as exc:
                raise serializers.ValidationError({'kit_id': 'Kit not found.'}) from exc
            recipient = user_kit.user

        if recipient == request.user:
            raise serializers.ValidationError('You cannot start a conversation with yourself.')

        attrs['recipient'] = recipient
        return attrs


class MessageWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['body']

    def validate_body(self, value):
        cleaned = (value or '').strip()
        if not cleaned:
            raise serializers.ValidationError('Message cannot be empty.')
        return cleaned


class ConversationDetailSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'other_user', 'created_at', 'updated_at']

    def get_other_user(self, obj):
        request = self.context.get('request')
        other_user = obj.get_other_participant(request.user) if request else None
        return ConversationUserSerializer(other_user, context=self.context).data if other_user else None


class ConversationListSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    last_message_created_at = serializers.DateTimeField(read_only=True)
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'other_user', 'last_message_preview', 'last_message_created_at', 'updated_at', 'unread_count']

    def get_other_user(self, obj):
        request = self.context.get('request')
        other_user = obj.get_other_participant(request.user) if request else None
        return ConversationUserSerializer(other_user, context=self.context).data if other_user else None

    def get_last_message_preview(self, obj):
        return getattr(obj, 'last_message_preview', '') or ''

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0

        unread_queryset = getattr(obj, 'unread_messages', None)
        if unread_queryset is not None:
            return len(unread_queryset)

        return obj.messages.filter(
            read_at__isnull=True
        ).exclude(
            sender=request.user
        ).count()


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'sender_id', 'sender_username', 'body', 'created_at', 'is_mine']

    def get_is_mine(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.sender_id == request.user.id)


class NotificationActorSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(source='profile.avatar', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'avatar']


class NotificationKitSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='user.username', read_only=True)
    team_name = serializers.CharField(source='kit.team.name', read_only=True)
    season = serializers.CharField(source='kit.season', read_only=True)
    kit_type = serializers.CharField(source='kit.kit_type', read_only=True)
    preview_image = serializers.SerializerMethodField()

    class Meta:
        model = UserKit
        fields = ['id', 'owner_username', 'team_name', 'season', 'kit_type', 'preview_image']

    def get_preview_image(self, obj):
        preview_image = None
        prefetched_images = getattr(obj, 'prefetched_notification_images', None)
        if prefetched_images is not None:
            if prefetched_images:
                preview_image = prefetched_images[0]
        else:
            preview_image = obj.images.order_by('order', 'created_at', 'id').first()

        if not preview_image:
            return None

        image_url = preview_image.image.url
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(image_url)
        return image_url


class NotificationCommentSerializer(serializers.ModelSerializer):
    body_preview = serializers.SerializerMethodField()
    author_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = KitComment
        fields = ['id', 'body_preview', 'author_username']

    def get_body_preview(self, obj):
        body = (obj.body or '').strip()
        if len(body) <= 80:
            return body
        return f"{body[:77].rstrip()}..."


class NotificationSerializer(serializers.ModelSerializer):
    actor = NotificationActorSerializer(read_only=True)
    kit = NotificationKitSerializer(read_only=True)
    comment = NotificationCommentSerializer(read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'type', 'actor', 'kit', 'comment', 'created_at', 'read_at', 'is_read']

    def get_is_read(self, obj):
        return obj.read_at is not None


class CollectionValueSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionValueSnapshot
        fields = ['id', 'created_at', 'total_value', 'kits_count', 'reason']

# Team Serializer
class TeamSerializer(serializers.ModelSerializer):
    slug = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ['id', 'name', 'slug', 'logo', 'league']

    def get_slug(self, obj):
        return build_team_slug(obj.name)

# Country Serializer
class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'flag']

# League Serializer
class LeagueSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)

    class Meta:
        model = League
        fields = ['id', 'name', 'hex_color', 'country', 'logo']

# Kit Serializer
class KitSerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)

    class Meta:
        model = Kit
        fields = ['id', 'team', 'season', 'kit_type', 'estimated_price', 'main_image']


class KitSearchSuggestionSerializer(serializers.Serializer):
    team_id = serializers.IntegerField(read_only=True)
    team_name = serializers.CharField(read_only=True)
    team_slug = serializers.CharField(read_only=True)
    season = serializers.CharField(read_only=True)
    kit_type = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)
    url = serializers.CharField(read_only=True)
    preview_image = serializers.CharField(read_only=True, allow_null=True)
    has_uploads = serializers.BooleanField(read_only=True)

# UserKit Image Serializer
class UserKitImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserKitImage
        fields = ['id', 'image', 'created_at']

# UserKit Serializer
class UserKitSerializer(serializers.ModelSerializer):
    PRIVATE_NOTE_MAX_LENGTH = 2000

    # Read-only nested serializers
    kit = KitSerializer(read_only=True)
    images = UserKitImageSerializer(many=True, read_only=True)

    size_display = serializers.CharField(source='get_size_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    technology_display = serializers.CharField(source='get_shirt_technology_display', read_only=True)

    likes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField() # To check if the current user liked this UserKit
    valuation_warning = serializers.SerializerMethodField()
    has_private_note = serializers.SerializerMethodField()

    # Write-only fields for creating/updating UserKit
    team_name = serializers.CharField(write_only=True)
    season = serializers.CharField(write_only=True)
    kit_type = serializers.CharField(write_only=True)
    new_images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    deleted_images = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    images_order = serializers.CharField(write_only=True, required=False)

    # Not in the model
    is_owner = serializers.SerializerMethodField()

    owner_id = serializers.IntegerField(source='user.id', read_only=True)
    owner_username = serializers.ReadOnlyField(source='user.username')
    owner_avatar = serializers.ImageField(source='user.profile.avatar', read_only=True, allow_null=True)

    class Meta:
        model = UserKit
        fields = [
            'id', 'user', 
            # Read-only fields
            'kit', 'images', 'condition_display', 'technology_display', 'final_value', 'size_display', 'added_at', 'is_owner', 'owner_id', 'owner_username', 'owner_avatar',
            # Write-only fields
            'team_name', 'season', 'kit_type', 'new_images', 'deleted_images', 'images_order',
            # Modifiable fields
            'condition', 'shirt_technology', 'size', 'for_sale', 'manual_value', 'likes_count', 'comments_count', 'is_liked', 'valuation_warning', 'player_name', 'player_number', 'private_note', 'offer_link', 'in_the_collection', 'has_private_note'
        ]
        read_only_fields = ['user', 'final_value', 'kit', 'images', 'condition_display', 'technology_display', 'size_display', 'added_at', 'is_owner', 'owner_id', 'owner_username', 'owner_avatar', 'likes_count', 'comments_count', 'is_liked', 'valuation_warning', 'has_private_note']
    
    # Getting is_owner field
    def get_is_owner(self, obj):
        request = self.context.get('request', None)
        if request and hasattr(request, 'user'):
            return obj.user == request.user
        return False

    # Getting is_liked field
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_comments_count(self, obj):
        return getattr(obj, 'comments_count', obj.comments.count())

    def get_valuation_warning(self, obj):
        return obj.get_valuation_warning()

    def get_has_private_note(self, obj):
        return bool((obj.private_note or '').strip()) if self.get_is_owner(obj) else False

    def validate_private_note(self, value):
        cleaned = (value or '').strip()
        if len(cleaned) > self.PRIVATE_NOTE_MAX_LENGTH:
            raise serializers.ValidationError(
                f'Private note cannot be longer than {self.PRIVATE_NOTE_MAX_LENGTH} characters.'
            )
        return cleaned

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        if self.get_is_owner(instance):
            representation['has_private_note'] = bool((instance.private_note or '').strip())
        else:
            representation.pop('private_note', None)
            representation.pop('has_private_note', None)

        return representation

    # Override create method to handle nested kit creation
    def create(self, validated_data):
        team_name = validated_data.pop('team_name')
        season = validated_data.pop('season')
        kit_type = validated_data.pop('kit_type')
        if 'in_the_collection' not in self.initial_data:
            validated_data['in_the_collection'] = True

        # Get or create the Team
        # team, _ = Team.objects.get_or_create(name=team_name.title()) - WRONG FC Barcelona -> Fc Barcelona
        clean_team_name = team_name.strip()

        team = Team.objects.filter(name__iexact=clean_team_name).first()
        if not team:
            team = Team.objects.create(name=clean_team_name)

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
    
    def update(self, instance, validated_data):
        # Handling Kit update (team_name, season, kit_type)
        team_name = validated_data.pop('team_name', None)
        season = validated_data.pop('season', None)
        kit_type = validated_data.pop('kit_type', None)

        if team_name and season and kit_type:
            
            clean_name = team_name.strip()

            team = Team.objects.filter(name__iexact=clean_name).first()

            if not team:
                team = Team.objects.create(name=clean_name)

            kit, _ = Kit.objects.get_or_create(
                team=team, 
                season=season, 
                kit_type=kit_type, 
                defaults={'estimated_price': 0}
            )
            
            instance.kit = kit

        images_order_json = validated_data.pop('images_order', None)
        # photos data
        new_images = validated_data.pop('new_images', [])
        deleted_images_ids = validated_data.pop('deleted_images', [])

        # Deleting specified photos
        if deleted_images_ids:
            # Ensure we only delete photos from this specific set (security)
            instance.images.filter(id__in=deleted_images_ids).delete()

        # Adding new photos
        created_new_images = [] 
        for image in new_images:
            img_obj = UserKitImage.objects.create(user_kit=instance, image=image)
            created_new_images.append(img_obj)
        
        # UPDATING ORDER OF IMAGES
        if images_order_json:
            try:
                order_list = json.loads(images_order_json) # Converting string to list 
                
                # Iterating over the list and updating the 'order' field in the database
                for index, item in enumerate(order_list):
                    
                    # A: Old photo (just an ID)
                    if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
                        instance.images.filter(id=item).update(order=index)

                    # B: New photo (placeholder "new_X")
                    elif isinstance(item, str) and item.startswith('new_'):
                        try:
                            # Parse "new_0" -> take what is after 'new_' -> int(0)
                            new_img_idx = int(item.split('_')[1])
                            
                            # Check if such an index exists in our created_new_images list
                            if 0 <= new_img_idx < len(created_new_images):
                                # Retrieve the object from memory
                                img_obj = created_new_images[new_img_idx]
                                # Update its order
                                img_obj.order = index
                                img_obj.save()
                        except (IndexError, ValueError):
                            # Ignore errors if frontend sent something strange
                            pass
            except json.JSONDecodeError:
                pass

        # Standard update of the remaining fields (Team, Size, etc.)
        return super().update(instance, validated_data)

# Profile Serializer
class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', required=False)

    country_info = CountrySerializer(source='country', read_only=True)
    favorite_team_info = TeamSerializer(source='favorite_team', read_only=True)

    class Meta:
        model = Profile
        fields = [
            # User & System
            'username', 
            'is_pro', 
            'is_moderator', 
            'has_changed_username',
            'on_vacation', 
            
            # Personal Info
            'avatar', 
            'bio', 
            'name', 
            'surname',
            
            # Preferences
            'country',            # country id eg. 34 (for saving)
            'favorite_team',      # team id eg. 12 (for saving)
            'country_info',       # full country data (for reading)
            'favorite_team_info', # full team data (for reading)
            'preferred_size', 
            'currency',
            
            # Contact
            'contact_email',

            # Socials
            'facebook_link',
            'instagram_link', 
            'twitter_link', 
            'youTube_link', 
            'tiktok_link',
            
            # Marketplaces
            'vinted_link', 
            'ebay_link', 
            'depop_link', 
            'website_link'
        ]
        read_only_fields = ['is_pro', 'is_moderator', 'has_changed_username']

    def update(self, instance, validated_data):
        # Extract user data if present
        new_username = None
        if 'user' in validated_data and 'username' in validated_data['user']:
            new_username = validated_data['user']['username']
        elif 'username' in self.initial_data:
            new_username = self.initial_data['username']

        # Update username if provided
        if new_username and new_username != instance.user.username:

            # Check if user has changed username before
            if instance.has_changed_username:
                raise serializers.ValidationError({
                    "username": "You can only change your username once."
                })

            # check if available excluding current user
            if User.objects.filter(username__iexact=new_username).exclude(id=instance.user.id).exists():
                raise serializers.ValidationError({"username": "This username is already taken."})
            
            # update username
            instance.user.username = new_username
            instance.user.save()

            # set flag to prevent future changes
            instance.has_changed_username = True
            instance.save()

        # Prevent changing the user field
        if 'user' in validated_data:
            validated_data.pop('user')

        # Update other profile fields
        return super().update(instance, validated_data)

# User serializer
class UserSerializer(serializers.ModelSerializer):
    # Nested profile serializer
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'profile']

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

# User Search Serializer with kits count
class UserSearchSerializer(serializers.ModelSerializer):
    kits_count = serializers.IntegerField(read_only=True)
    followers_count = serializers.IntegerField(read_only=True, default=0)
    avatar = serializers.ImageField(source='profile.avatar', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'kits_count', 'avatar', 'followers_count']

# User Stats Profile Serializer
class UserStatsProfileSerializer(serializers.ModelSerializer):
    date_joined = serializers.DateTimeField(read_only=True)
    total_kits = serializers.IntegerField(read_only=True)
    total_value = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    # --- Social ---
    followers_count = serializers.IntegerField(read_only=True, default=0)
    following_count = serializers.IntegerField(read_only=True, default=0)
    is_followed_by_me = serializers.BooleanField(read_only=True, default=False)

    # --- Profile Basic Info ---
    avatar = serializers.ImageField(source='profile.avatar', read_only=True)
    bio = serializers.CharField(source='profile.bio', read_only=True)
    name = serializers.CharField(source='profile.name', read_only=True)
    surname = serializers.CharField(source='profile.surname', read_only=True)

    # --- Status ---
    is_pro = serializers.BooleanField(source='profile.is_pro', read_only=True)
    is_moderator = serializers.BooleanField(source='profile.is_moderator', read_only=True)
    on_vacation = serializers.BooleanField(source='profile.on_vacation', read_only=True)

    # --- Preferences (Full Objects for display) ---
    country_info = CountrySerializer(source='profile.country', read_only=True)
    favorite_team_info = TeamSerializer(source='profile.favorite_team', read_only=True)
    preferred_size = serializers.CharField(source='profile.preferred_size', read_only=True)

    # --- Contact ---
    contact_email = serializers.EmailField(source='profile.contact_email', read_only=True)
    website_link = serializers.URLField(source='profile.website_link', read_only=True)

    # --- Social Media ---
    facebook_link = serializers.URLField(source='profile.facebook_link', read_only=True)
    instagram_link = serializers.URLField(source='profile.instagram_link', read_only=True)
    twitter_link = serializers.URLField(source='profile.twitter_link', read_only=True)
    youTube_link = serializers.URLField(source='profile.youTube_link', read_only=True)
    tiktok_link = serializers.URLField(source='profile.tiktok_link', read_only=True)
    
    # --- Marketplaces ---
    vinted_link = serializers.URLField(source='profile.vinted_link', read_only=True)
    ebay_link = serializers.URLField(source='profile.ebay_link', read_only=True)
    depop_link = serializers.URLField(source='profile.depop_link', read_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'date_joined', 
            'total_kits', 'total_value',

            # Social
            'followers_count', 'following_count', 'is_followed_by_me',
            
            # Profile Fields
            'avatar', 'bio', 'name', 'surname',
            'is_pro', 'is_moderator', 'on_vacation',
            
            # Details
            'country_info',
            'favorite_team_info',
            'preferred_size',
            
            # Links
            'contact_email', 'website_link',
            'facebook_link', 'instagram_link', 'twitter_link', 'youTube_link', 'tiktok_link',
            'vinted_link', 'ebay_link', 'depop_link'
        ]
