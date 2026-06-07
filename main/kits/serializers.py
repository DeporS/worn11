from rest_framework import serializers
from .models import Country, League, Team, Kit, KitType, KitTypeAlias, UserKit, UserKitImage, WishlistItem, User, Profile, KitComment, KitReport, Conversation, Message, Notification, CollectionValueSnapshot, ShirtVersion, CANONICAL_WISHLIST_KIT_TYPES, build_team_slug, normalize_wishlist_kit_type
from django.contrib.auth.models import User
from dj_rest_auth.serializers import UserDetailsSerializer
import json
from urllib.parse import urlencode


def normalize_catalog_name(value):
    return ' '.join((value or '').strip().lower().split())


def resolve_approved_kit_type(*, kit_type_id=None, kit_type_slug=None, legacy_name=None):
    queryset = KitType.objects.filter(status=KitType.STATUS_APPROVED)

    if kit_type_id not in (None, ''):
        try:
            resolved = queryset.filter(pk=int(kit_type_id)).first()
        except (TypeError, ValueError):
            resolved = None
        if resolved is None:
            raise serializers.ValidationError({'kit_type_id': 'Shirt type is invalid.'})
        return resolved

    if kit_type_slug not in (None, ''):
        resolved = queryset.filter(slug=str(kit_type_slug).strip()).first()
        if resolved is None:
            raise serializers.ValidationError({'kit_type_slug': 'Shirt type is invalid.'})
        return resolved

    normalized_name = normalize_catalog_name(legacy_name)
    if not normalized_name:
        return None

    resolved = queryset.filter(name__iexact=' '.join((legacy_name or '').strip().split())).first()
    if resolved is not None:
        return resolved

    alias = KitTypeAlias.objects.select_related('kit_type').filter(
        alias_normalized=normalized_name,
        kit_type__status=KitType.STATUS_APPROVED,
    ).first()
    return alias.kit_type if alias else None


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
    kit_type_id = serializers.IntegerField(source='kit_type_ref_id', read_only=True, allow_null=True)
    kit_type_slug = serializers.SerializerMethodField()
    kit_type_display = serializers.SerializerMethodField()
    kit_type_canonical_code = serializers.SerializerMethodField()

    class Meta:
        model = Kit
        fields = [
            'id',
            'team',
            'season',
            'kit_type',
            'kit_type_id',
            'kit_type_slug',
            'kit_type_display',
            'kit_type_canonical_code',
            'estimated_price',
            'main_image',
        ]

    def get_kit_type_slug(self, obj):
        return obj.kit_type_ref.slug if obj.kit_type_ref_id else None

    def get_kit_type_display(self, obj):
        return obj.kit_type_ref.name if obj.kit_type_ref_id else obj.kit_type

    def get_kit_type_canonical_code(self, obj):
        return obj.kit_type_ref.canonical_code if obj.kit_type_ref_id else None


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


class WishlistToggleSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()
    season = serializers.CharField()
    kit_type = serializers.CharField()
    source_userkit_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_team_id(self, value):
        team = Team.objects.filter(pk=value).first()
        if team is None:
            raise serializers.ValidationError('Team not found.')
        return value

    def validate_season(self, value):
        cleaned = ' '.join((value or '').strip().split())
        if not cleaned:
            raise serializers.ValidationError('Season is required.')
        return cleaned

    def validate_kit_type(self, value):
        normalized_type = normalize_wishlist_kit_type(value)
        dynamic_type = resolve_approved_kit_type(legacy_name=normalized_type)
        if normalized_type not in CANONICAL_WISHLIST_KIT_TYPES and dynamic_type is None:
            raise serializers.ValidationError('Kit type is invalid.')
        return dynamic_type.name if dynamic_type is not None else normalized_type

    def validate_source_userkit_id(self, value):
        if value is None:
            return None

        if not UserKit.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Source kit not found.')
        return value

    def validate(self, attrs):
        source_userkit_id = attrs.get('source_userkit_id')
        if source_userkit_id is None:
            return attrs

        source_userkit = UserKit.objects.select_related('kit', 'kit__team').filter(pk=source_userkit_id).first()
        if source_userkit is None:
            raise serializers.ValidationError({'source_userkit_id': 'Source kit not found.'})

        source_kit_type = normalize_wishlist_kit_type(source_userkit.kit.kit_type)
        if (
            source_userkit.kit.team_id != attrs['team_id']
            or source_userkit.kit.season != attrs['season']
            or source_kit_type != attrs['kit_type']
        ):
            raise serializers.ValidationError({
                'source_userkit_id': 'Source kit must match the same team, season, and kit type.',
            })

        attrs['source_userkit'] = source_userkit
        return attrs


class WishlistItemSerializer(serializers.ModelSerializer):
    team_id = serializers.IntegerField(source='team.id', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    team_slug = serializers.SerializerMethodField()
    source_userkit_id = serializers.IntegerField(source='source_userkit.id', read_only=True)
    preview_image = serializers.SerializerMethodField()
    has_uploads = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source='user.username', read_only=True)
    url = serializers.SerializerMethodField()
    kit_type_id = serializers.IntegerField(source='kit_type_ref_id', read_only=True, allow_null=True)
    kit_type_slug = serializers.SerializerMethodField()
    kit_type_display = serializers.SerializerMethodField()
    kit_type_canonical_code = serializers.SerializerMethodField()

    class Meta:
        model = WishlistItem
        fields = [
            'id',
            'team_id',
            'team_name',
            'team_slug',
            'season',
            'kit_type',
            'kit_type_id',
            'kit_type_slug',
            'kit_type_display',
            'kit_type_canonical_code',
            'source_userkit_id',
            'preview_image',
            'has_uploads',
            'created_at',
            'owner_username',
            'url',
        ]

    def get_team_slug(self, obj):
        return build_team_slug(obj.team.name)

    def get_kit_type_slug(self, obj):
        return obj.kit_type_ref.slug if obj.kit_type_ref_id else None

    def get_kit_type_display(self, obj):
        return obj.kit_type_ref.name if obj.kit_type_ref_id else obj.kit_type

    def get_kit_type_canonical_code(self, obj):
        return obj.kit_type_ref.canonical_code if obj.kit_type_ref_id else None

    def get_preview_image(self, obj):
        preview_map = self.context.get('wishlist_preview_map', {})
        return preview_map.get((obj.team_id, obj.season, obj.kit_type))

    def get_has_uploads(self, obj):
        preview_map = self.context.get('wishlist_preview_map', {})
        return (obj.team_id, obj.season, obj.kit_type) in preview_map

    def get_url(self, obj):
        return f"/history/team/{build_team_slug(obj.team.name)}/variants?{urlencode({'season': obj.season, 'type': obj.kit_type})}"

# UserKit Image Serializer
class UserKitImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserKitImage
        fields = ['id', 'image', 'created_at']

# UserKit Serializer
class UserKitSerializer(serializers.ModelSerializer):
    PRIVATE_NOTE_MAX_LENGTH = 2000
    LEGACY_VERSION_CODES = {'REPLICA', 'PLAYER_ISSUE', 'MATCH_WORN'}

    # Read-only nested serializers
    kit = KitSerializer(read_only=True)
    images = UserKitImageSerializer(many=True, read_only=True)

    size_display = serializers.CharField(source='get_size_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    technology_display = serializers.CharField(source='get_shirt_technology_display', read_only=True)
    shirt_version_id = serializers.IntegerField(read_only=True, allow_null=True)
    shirt_version_code = serializers.SerializerMethodField()
    shirt_version_display = serializers.SerializerMethodField()
    shirt_version_manual_value_recommended = serializers.SerializerMethodField()
    shirt_version_valuation_note = serializers.SerializerMethodField()

    likes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField() # To check if the current user liked this UserKit
    valuation_warning = serializers.SerializerMethodField()
    has_private_note = serializers.SerializerMethodField()

    # Write-only fields for creating/updating UserKit
    team_name = serializers.CharField(write_only=True)
    season = serializers.CharField(write_only=True)
    kit_type = serializers.CharField(write_only=True, required=False)
    kit_type_id = serializers.IntegerField(write_only=True, required=False)
    kit_type_slug = serializers.CharField(write_only=True, required=False)
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
            'kit', 'images', 'condition_display', 'technology_display', 'shirt_version_id', 'shirt_version_code', 'shirt_version_display', 'shirt_version_manual_value_recommended', 'shirt_version_valuation_note', 'final_value', 'size_display', 'added_at', 'is_owner', 'owner_id', 'owner_username', 'owner_avatar',
            # Write-only fields
            'team_name', 'season', 'kit_type', 'kit_type_id', 'kit_type_slug', 'new_images', 'deleted_images', 'images_order',
            # Modifiable fields
            'condition', 'shirt_technology', 'size', 'for_sale', 'manual_value', 'likes_count', 'comments_count', 'is_liked', 'valuation_warning', 'player_name', 'player_number', 'private_note', 'offer_link', 'in_the_collection', 'has_private_note'
        ]
        read_only_fields = ['user', 'final_value', 'kit', 'images', 'condition_display', 'technology_display', 'shirt_version_id', 'shirt_version_code', 'shirt_version_display', 'shirt_version_manual_value_recommended', 'shirt_version_valuation_note', 'size_display', 'added_at', 'is_owner', 'owner_id', 'owner_username', 'owner_avatar', 'likes_count', 'comments_count', 'is_liked', 'valuation_warning', 'has_private_note']
        extra_kwargs = {
            'shirt_technology': {'required': False},
        }
    
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

    def get_shirt_version_code(self, obj):
        return obj.shirt_version.code if obj.shirt_version_id else obj.shirt_technology

    def get_shirt_version_display(self, obj):
        return obj.shirt_version.name if obj.shirt_version_id else obj.get_shirt_technology_display()

    def get_shirt_version_manual_value_recommended(self, obj):
        return obj.shirt_version.manual_value_recommended if obj.shirt_version_id else False

    def get_shirt_version_valuation_note(self, obj):
        return obj.shirt_version.valuation_note if obj.shirt_version_id else ''

    def get_has_private_note(self, obj):
        return bool((obj.private_note or '').strip()) if self.get_is_owner(obj) else False

    def validate_private_note(self, value):
        cleaned = (value or '').strip()
        if len(cleaned) > self.PRIVATE_NOTE_MAX_LENGTH:
            raise serializers.ValidationError(
                f'Private note cannot be longer than {self.PRIVATE_NOTE_MAX_LENGTH} characters.'
            )
        return cleaned

    def validate(self, attrs):
        attrs = super().validate(attrs)
        raw_type_id = attrs.pop('kit_type_id', None)
        raw_type_slug = attrs.pop('kit_type_slug', None)
        legacy_type = attrs.get('kit_type')
        requested_kit_type = resolve_approved_kit_type(
            kit_type_id=raw_type_id,
            kit_type_slug=raw_type_slug,
            legacy_name=legacy_type,
        )

        if requested_kit_type is not None:
            attrs['resolved_kit_type'] = requested_kit_type
            attrs['kit_type'] = requested_kit_type.name
        elif self.instance is None and not legacy_type:
            raise serializers.ValidationError({'kit_type': 'Shirt type is required.'})

        raw_code = self.initial_data.get('shirt_version_code')
        raw_id = self.initial_data.get('shirt_version_id')
        requested_version = None

        if raw_code not in (None, ''):
            requested_version = ShirtVersion.objects.filter(
                code=str(raw_code).strip(),
                is_active=True,
            ).first()
            if requested_version is None:
                raise serializers.ValidationError({
                    'shirt_version_code': 'Shirt version is invalid or inactive.'
                })

        if raw_id not in (None, ''):
            try:
                requested_by_id = ShirtVersion.objects.filter(
                    pk=int(raw_id),
                    is_active=True,
                ).first()
            except (TypeError, ValueError):
                requested_by_id = None

            if requested_by_id is None:
                raise serializers.ValidationError({
                    'shirt_version_id': 'Shirt version is invalid or inactive.'
                })
            if requested_version is not None and requested_version.pk != requested_by_id.pk:
                raise serializers.ValidationError({
                    'shirt_version_id': 'Shirt version id and code do not match.'
                })
            requested_version = requested_by_id

        legacy_code = attrs.get('shirt_technology')
        if requested_version is None and legacy_code:
            requested_version = ShirtVersion.objects.filter(
                code=legacy_code,
                is_active=True,
            ).first()

        if requested_version is not None:
            attrs['shirt_version'] = requested_version
            if requested_version.code in self.LEGACY_VERSION_CODES:
                attrs['shirt_technology'] = requested_version.code
            elif self.instance is None:
                attrs['shirt_technology'] = 'REPLICA'
            else:
                attrs.pop('shirt_technology', None)
        elif self.instance is None and not legacy_code:
            raise serializers.ValidationError({
                'shirt_version_code': 'Shirt version is required.'
            })

        return attrs

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
        kit_type_ref = validated_data.pop('resolved_kit_type', None)
        if 'in_the_collection' not in self.initial_data:
            validated_data['in_the_collection'] = True

        # Get or create the Team
        # team, _ = Team.objects.get_or_create(name=team_name.title()) - WRONG FC Barcelona -> Fc Barcelona
        clean_team_name = team_name.strip()

        team = Team.objects.filter(name__iexact=clean_team_name).first()
        if not team:
            team = Team.objects.create(name=clean_team_name)

        # Get or create the Kit
        kit, _ = Kit.objects.get_or_create(
            team=team,
            season=season,
            kit_type=kit_type,
            defaults={'estimated_price': 0, 'kit_type_ref': kit_type_ref},
        )
        if kit_type_ref is not None and kit.kit_type_ref_id != kit_type_ref.id:
            kit.kit_type_ref = kit_type_ref
            kit.save(update_fields=['kit_type_ref'])

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
        kit_type_ref = validated_data.pop('resolved_kit_type', None)

        if team_name and season and kit_type:
            
            clean_name = team_name.strip()

            team = Team.objects.filter(name__iexact=clean_name).first()

            if not team:
                team = Team.objects.create(name=clean_name)

            kit, _ = Kit.objects.get_or_create(
                team=team, 
                season=season, 
                kit_type=kit_type, 
                defaults={'estimated_price': 0, 'kit_type_ref': kit_type_ref}
            )
            if kit_type_ref is not None and kit.kit_type_ref_id != kit_type_ref.id:
                kit.kit_type_ref = kit_type_ref
                kit.save(update_fields=['kit_type_ref'])
            
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
