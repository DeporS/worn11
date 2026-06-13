from rest_framework import serializers
from .models import Country, League, Team, Kit, KitType, KitTypeAlias, TeamSeasonKitType, KitTypeModerationAction, TeamModerationAction, UserKit, UserKitImage, WishlistItem, User, Profile, KitComment, KitReport, KitReportModerationAction, Conversation, Message, Notification, CollectionValueSnapshot, ShirtVersion, CANONICAL_WISHLIST_KIT_TYPES, build_team_slug, normalize_wishlist_kit_type
from django.contrib.auth.models import User
from dj_rest_auth.serializers import UserDetailsSerializer
from django.utils.text import slugify
import re
import json
from urllib.parse import urlencode
from .permissions import can_undo_moderation_action, can_view_collection_value, moderation_action_is_currently_undoable, is_staff_or_moderator
from .team_season_suggestions import ensure_team_season_suggestion


HEX_COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')


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


def build_unique_kit_type_slug(name):
    base_slug = slugify(name or '')[:110] or 'kit-type'
    candidate = base_slug
    suffix = 2

    while KitType.objects.filter(slug=candidate).exists():
        suffix_text = f'-{suffix}'
        candidate = f'{base_slug[:120 - len(suffix_text)]}{suffix_text}'
        suffix += 1

    return candidate


def build_userkit_title(userkit):
    if userkit is None or getattr(userkit, 'kit', None) is None:
        return ''

    parts = [
        getattr(getattr(userkit.kit, 'team', None), 'name', ''),
        userkit.kit.season,
        userkit.kit.kit_type,
    ]
    return ' '.join(part for part in parts if part).strip()


def get_or_create_pending_kit_type(*, legacy_name, created_by=None):
    cleaned_name = ' '.join((legacy_name or '').strip().split())
    if not cleaned_name:
        return None

    existing = KitType.objects.filter(name__iexact=cleaned_name).exclude(
        status=KitType.STATUS_MERGED,
    ).order_by('id').first()
    if existing is not None:
        return existing

    return KitType.objects.create(
        name=cleaned_name,
        slug=build_unique_kit_type_slug(cleaned_name),
        category=KitType.CATEGORY_OTHER,
        status=KitType.STATUS_PENDING,
        default_visibility=KitType.VISIBILITY_NONE,
        created_by=created_by,
    )


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

        return obj.user_id == request.user.id or is_staff_or_moderator(request.user)

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


class AdminKitReportDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_note(self, value):
        return (value or '').strip()


class AdminKitReportReporterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class AdminKitReportItemSerializer(serializers.ModelSerializer):
    reporter = AdminKitReportReporterSerializer(read_only=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True)

    class Meta:
        model = KitReport
        fields = [
            'id',
            'reason',
            'description',
            'status',
            'reporter',
            'resolved_by_username',
            'resolution_note',
            'created_at',
            'updated_at',
        ]


class AdminKitReportModerationActionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = KitReportModerationAction
        fields = [
            'id',
            'action_type',
            'actor_username',
            'report_ids',
            'note',
            'created_at',
        ]


class AdminKitReportGroupListSerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(source='user.id', read_only=True)
    owner_username = serializers.CharField(source='user.username', read_only=True)
    team_name = serializers.CharField(source='kit.team.name', read_only=True)
    season = serializers.CharField(source='kit.season', read_only=True)
    kit_type = serializers.CharField(source='kit.kit_type', read_only=True)
    preview_image = serializers.SerializerMethodField()
    report_count = serializers.SerializerMethodField()
    pending_report_count = serializers.SerializerMethodField()
    latest_report_at = serializers.SerializerMethodField()
    reasons = serializers.SerializerMethodField()
    reporters = serializers.SerializerMethodField()
    latest_reports = serializers.SerializerMethodField()
    has_pending_reports = serializers.SerializerMethodField()

    class Meta:
        model = UserKit
        fields = [
            'id',
            'owner_id',
            'owner_username',
            'team_name',
            'season',
            'kit_type',
            'preview_image',
            'is_hidden_by_moderation',
            'report_count',
            'pending_report_count',
            'latest_report_at',
            'reasons',
            'reporters',
            'latest_reports',
            'has_pending_reports',
        ]

    def _get_reports(self, obj):
        return list(getattr(obj, 'prefetched_report_group_reports', []))

    def get_preview_image(self, obj):
        first_image = obj.images.order_by('order', 'created_at', 'id').first()
        if first_image is None:
            return None
        request = self.context.get('request')
        image_url = first_image.image.url
        if request is not None:
            return request.build_absolute_uri(image_url)
        return image_url

    def get_report_count(self, obj):
        return len(self._get_reports(obj))

    def get_pending_report_count(self, obj):
        return sum(1 for report in self._get_reports(obj) if report.status == 'pending')

    def get_latest_report_at(self, obj):
        reports = self._get_reports(obj)
        return reports[0].created_at if reports else None

    def get_reasons(self, obj):
        seen = []
        for report in self._get_reports(obj):
            if report.reason not in seen:
                seen.append(report.reason)
        return seen

    def get_reporters(self, obj):
        reporters = []
        seen = set()
        for report in self._get_reports(obj):
            reporter = getattr(report, 'reporter', None)
            if reporter is None or reporter.id in seen:
                continue
            seen.add(reporter.id)
            reporters.append({
                'id': reporter.id,
                'username': reporter.username,
            })
        return reporters

    def get_latest_reports(self, obj):
        reports = self._get_reports(obj)[:3]
        return AdminKitReportItemSerializer(reports, many=True).data

    def get_has_pending_reports(self, obj):
        return any(report.status == 'pending' for report in self._get_reports(obj))


class AdminKitReportGroupDetailSerializer(AdminKitReportGroupListSerializer):
    reports = serializers.SerializerMethodField()
    moderation_actions = serializers.SerializerMethodField()
    moderation_hidden_reason = serializers.CharField(read_only=True)

    class Meta(AdminKitReportGroupListSerializer.Meta):
        fields = AdminKitReportGroupListSerializer.Meta.fields + [
            'moderation_hidden_reason',
            'reports',
            'moderation_actions',
        ]

    def get_reports(self, obj):
        return AdminKitReportItemSerializer(self._get_reports(obj), many=True).data

    def get_moderation_actions(self, obj):
        actions = list(getattr(obj, 'prefetched_report_moderation_actions', []))
        return AdminKitReportModerationActionSerializer(actions, many=True).data


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
    title = serializers.SerializerMethodField()
    preview_image = serializers.SerializerMethodField()

    class Meta:
        model = UserKit
        fields = ['id', 'owner_username', 'team_name', 'season', 'kit_type', 'title', 'preview_image']

    def get_title(self, obj):
        return build_userkit_title(obj)

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
    moderation_note = serializers.SerializerMethodField()
    target_path = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'type', 'actor', 'kit', 'comment', 'moderation_note', 'target_path', 'created_at', 'read_at', 'is_read']

    def get_is_read(self, obj):
        return obj.read_at is not None

    def get_moderation_note(self, obj):
        if obj.type != 'moderation_kit_removed' or obj.kit_id is None:
            return ''
        return (obj.kit.moderation_hidden_reason or '').strip()

    def get_target_path(self, obj):
        if obj.type == 'moderation_kit_removed' and obj.kit_id is not None:
            return f'/removed-kits/{obj.kit_id}'

        if obj.type in {'kit_like', 'kit_comment', 'comment_like', 'comment_reply'} and obj.kit_id is not None:
            owner_username = getattr(getattr(obj, 'kit', None), 'user', None).username if getattr(getattr(obj, 'kit', None), 'user', None) else ''
            if owner_username:
                return f'/profile/{owner_username}/kits/{obj.kit_id}'

        if obj.type == 'follow' and obj.actor_id is not None:
            return f'/profile/{obj.actor.username}'

        return ''


class RemovedKitDetailSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    team = serializers.CharField(source='kit.team.name', read_only=True)
    title = serializers.SerializerMethodField()
    season = serializers.CharField(source='kit.season', read_only=True)
    kit_type = serializers.CharField(source='kit.kit_type', read_only=True)
    removed_at = serializers.DateTimeField(source='hidden_by_moderation_at', read_only=True)
    removed_by_moderation = serializers.SerializerMethodField()
    moderation_note = serializers.CharField(source='moderation_hidden_reason', read_only=True)
    moderation_reason = serializers.CharField(source='moderation_hidden_reason', read_only=True)
    can_restore = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = UserKit
        fields = [
            'id',
            'title',
            'team',
            'season',
            'kit_type',
            'images',
            'removed_at',
            'removed_by_moderation',
            'moderation_note',
            'moderation_reason',
            'can_restore',
            'can_edit',
        ]

    def get_title(self, obj):
        return build_userkit_title(obj)

    def get_images(self, obj):
        return UserKitImageSerializer(obj.images.all(), many=True, context=self.context).data

    def get_removed_by_moderation(self, obj):
        return bool(obj.is_hidden_by_moderation)

    def get_can_restore(self, obj):
        return False

    def get_can_edit(self, obj):
        return False


class CollectionValueSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionValueSnapshot
        fields = ['id', 'created_at', 'total_value', 'kits_count', 'reason']

# Team Serializer
class TeamSerializer(serializers.ModelSerializer):
    slug = serializers.SerializerMethodField()
    country_id = serializers.IntegerField(read_only=True, allow_null=True)
    country_name = serializers.CharField(source='country.name', read_only=True, allow_null=True)
    country_code = serializers.CharField(source='country.code', read_only=True, allow_null=True)
    league_id = serializers.IntegerField(read_only=True, allow_null=True)
    league_name = serializers.CharField(source='league.name', read_only=True, allow_null=True)

    class Meta:
        model = Team
        fields = [
            'id',
            'name',
            'slug',
            'logo',
            'league',
            'country_id',
            'country_name',
            'country_code',
            'league_id',
            'league_name',
        ]

    def get_slug(self, obj):
        return build_team_slug(obj.name)

# Country Serializer
class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'flag', 'is_active']

# League Serializer
class LeagueSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    country_id = serializers.IntegerField(read_only=True, allow_null=True)
    country_name = serializers.CharField(source='country.name', read_only=True, allow_null=True)
    country_code = serializers.CharField(source='country.code', read_only=True, allow_null=True)

    class Meta:
        model = League
        fields = [
            'id',
            'name',
            'hex_color',
            'country',
            'country_id',
            'country_name',
            'country_code',
            'logo',
            'order',
            'is_active',
        ]

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


class AdminKitTypeSuggestionSerializer(serializers.ModelSerializer):
    team_id = serializers.IntegerField(source='team.id', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    team_slug = serializers.SerializerMethodField()
    kit_type_id = serializers.IntegerField(source='kit_type.id', read_only=True)
    kit_type_name = serializers.CharField(source='kit_type.name', read_only=True)
    kit_type_slug = serializers.CharField(source='kit_type.slug', read_only=True)
    kit_type_status = serializers.CharField(source='kit_type.status', read_only=True)
    team_season_status = serializers.CharField(source='status', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    upload_count = serializers.IntegerField(read_only=True)
    preview_image = serializers.SerializerMethodField()
    museum_url = serializers.SerializerMethodField()
    example_source_userkit_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = TeamSeasonKitType
        fields = [
            'id',
            'team_id',
            'team_name',
            'team_slug',
            'season',
            'kit_type_id',
            'kit_type_name',
            'kit_type_slug',
            'kit_type_status',
            'team_season_status',
            'source',
            'created_by_username',
            'created_at',
            'upload_count',
            'preview_image',
            'museum_url',
            'example_source_userkit_id',
        ]

    def get_team_slug(self, obj):
        return build_team_slug(obj.team.name)

    def get_preview_image(self, obj):
        request = self.context.get('request')
        preview_image = getattr(obj, 'preview_image', None)
        if not preview_image:
            return None
        return request.build_absolute_uri(preview_image) if request else preview_image

    def get_museum_url(self, obj):
        query_string = urlencode({'season': obj.season, 'type': obj.kit_type.name})
        return f"/history/team/{build_team_slug(obj.team.name)}/variants?{query_string}"


class AdminKitTypeMergeSerializer(serializers.Serializer):
    target_kit_type_id = serializers.IntegerField()

    def validate_target_kit_type_id(self, value):
        target = KitType.objects.filter(
            pk=value,
            status=KitType.STATUS_APPROVED,
        ).first()
        if target is None:
            raise serializers.ValidationError('Target shirt type must be an approved KitType.')
        self.context['target_kit_type'] = target
        return value


class SimilarVerifiedTeamSerializer(serializers.ModelSerializer):
    slug = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ['id', 'name', 'slug', 'logo']

    def get_slug(self, obj):
        return build_team_slug(obj.name)


class TeamModerationListSerializer(serializers.ModelSerializer):
    slug = serializers.SerializerMethodField()
    league = serializers.SerializerMethodField()
    usage = serializers.SerializerMethodField()
    country_id = serializers.IntegerField(read_only=True, allow_null=True)
    country_name = serializers.CharField(source='country.name', read_only=True, allow_null=True)
    country_code = serializers.CharField(source='country.code', read_only=True, allow_null=True)
    league_id = serializers.IntegerField(read_only=True, allow_null=True)
    league_name = serializers.CharField(source='league.name', read_only=True, allow_null=True)
    preview_image = serializers.SerializerMethodField()
    similar_verified_teams = serializers.SerializerMethodField()
    seasons = serializers.SerializerMethodField()
    kits_count = serializers.IntegerField(read_only=True)
    userkits_count = serializers.IntegerField(read_only=True)
    unique_users_count = serializers.IntegerField(read_only=True)
    wishlist_count = serializers.IntegerField(read_only=True)
    favorite_team_count = serializers.IntegerField(read_only=True)
    can_reject = serializers.BooleanField(read_only=True)
    reject_block_reason = serializers.CharField(read_only=True)

    class Meta:
        model = Team
        fields = [
            'id',
            'name',
            'slug',
            'logo',
            'league',
            'usage',
            'country_id',
            'country_name',
            'country_code',
            'league_id',
            'league_name',
            'is_verified',
            'kits_count',
            'userkits_count',
            'unique_users_count',
            'wishlist_count',
            'favorite_team_count',
            'seasons',
            'preview_image',
            'can_reject',
            'reject_block_reason',
            'similar_verified_teams',
        ]

    def get_slug(self, obj):
        return build_team_slug(obj.name)

    def get_league(self, obj):
        if obj.league_id is None:
            return None
        return {
            'id': obj.league_id,
            'name': obj.league.name,
        }

    def get_preview_image(self, obj):
        request = self.context.get('request')
        preview_image = getattr(obj, 'preview_image', None)
        if not preview_image:
            return None
        return request.build_absolute_uri(preview_image) if request else preview_image

    def get_similar_verified_teams(self, obj):
        serializer = SimilarVerifiedTeamSerializer(
            getattr(obj, 'similar_verified_teams', []),
            many=True,
            context=self.context,
        )
        return serializer.data

    def get_seasons(self, obj):
        return getattr(obj, 'seasons', [])

    def get_usage(self, obj):
        usage = getattr(obj, 'usage', None)
        return usage if usage is not None else None


class TeamModerationMergeSerializer(serializers.Serializer):
    target_team_id = serializers.IntegerField()


class AdminCountryCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    code = serializers.CharField()

    def validate_name(self, value):
        cleaned = ' '.join((value or '').strip().split())
        if not cleaned:
            raise serializers.ValidationError('Country name is required.')
        return cleaned

    def validate_code(self, value):
        cleaned = (value or '').strip().upper()
        if not cleaned:
            raise serializers.ValidationError('Country code is required.')
        return cleaned


class AdminLeagueCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    country_id = serializers.IntegerField()

    def validate_name(self, value):
        cleaned = ' '.join((value or '').strip().split())
        if not cleaned:
            raise serializers.ValidationError('League name is required.')
        return cleaned

    def validate_country_id(self, value):
        if not Country.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError('Country must be an active country.')
        return value


class CatalogCountrySerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    leagues_count = serializers.IntegerField(read_only=True)
    teams_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Country
        fields = [
            'id',
            'name',
            'code',
            'flag',
            'is_active',
            'created_by',
            'created_at',
            'leagues_count',
            'teams_count',
        ]


class CatalogCountryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['name', 'code', 'flag', 'is_active']
        extra_kwargs = {
            'name': {'validators': []},
            'code': {'validators': []},
        }

    def validate_name(self, value):
        cleaned = ' '.join((value or '').strip().split())
        if not cleaned:
            raise serializers.ValidationError('Country name is required.')
        return cleaned

    def validate_code(self, value):
        cleaned = (value or '').strip().upper()
        if not cleaned:
            raise serializers.ValidationError('Country code is required.')
        return cleaned

    def validate(self, attrs):
        attrs = super().validate(attrs)
        return attrs


class CatalogLeagueSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    country_id = serializers.IntegerField(source='country.id', read_only=True, allow_null=True)
    country_name = serializers.CharField(source='country.name', read_only=True, allow_null=True)
    country_code = serializers.CharField(source='country.code', read_only=True, allow_null=True)
    teams_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = League
        fields = [
            'id',
            'name',
            'country_id',
            'country_name',
            'country_code',
            'logo',
            'hex_color',
            'order',
            'is_active',
            'created_by',
            'created_at',
            'teams_count',
        ]


class CatalogLeagueWriteSerializer(serializers.ModelSerializer):
    country_id = serializers.IntegerField()

    class Meta:
        model = League
        fields = ['name', 'country_id', 'logo', 'hex_color', 'order', 'is_active']
        extra_kwargs = {
            'name': {'validators': []},
        }

    def validate_name(self, value):
        cleaned = ' '.join((value or '').strip().split())
        if not cleaned:
            raise serializers.ValidationError('League name is required.')
        return cleaned

    def validate_hex_color(self, value):
        cleaned = (value or '').strip()
        if not cleaned:
            return '#333333'
        if not HEX_COLOR_PATTERN.match(cleaned):
            raise serializers.ValidationError('Color must be a valid hex code like #EF4444.')
        return cleaned.upper()

    def validate_country_id(self, value):
        country = Country.objects.filter(pk=value).first()
        if country is None:
            raise serializers.ValidationError('Country is invalid.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, 'instance', None)
        country_id = attrs.get('country_id', instance.country_id if instance is not None else None)

        country = Country.objects.filter(pk=country_id).first()
        if country is None:
            raise serializers.ValidationError({'country_id': 'Country is invalid.'})
        if instance is None and not country.is_active:
            raise serializers.ValidationError({'country_id': 'Country must be active.'})

        attrs['country'] = country
        return attrs


class CatalogTeamSerializer(serializers.ModelSerializer):
    slug = serializers.SerializerMethodField()
    country_id = serializers.IntegerField(source='country.id', read_only=True, allow_null=True)
    country_name = serializers.CharField(source='country.name', read_only=True, allow_null=True)
    country_code = serializers.CharField(source='country.code', read_only=True, allow_null=True)
    league_id = serializers.IntegerField(source='league.id', read_only=True, allow_null=True)
    league_name = serializers.CharField(source='league.name', read_only=True, allow_null=True)
    kits_count = serializers.IntegerField(read_only=True)
    userkits_count = serializers.IntegerField(read_only=True)
    wishlist_count = serializers.IntegerField(read_only=True)
    favorite_team_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Team
        fields = [
            'id',
            'name',
            'slug',
            'logo',
            'country_id',
            'country_name',
            'country_code',
            'league_id',
            'league_name',
            'is_verified',
            'kits_count',
            'userkits_count',
            'wishlist_count',
            'favorite_team_count',
        ]

    def get_slug(self, obj):
        return build_team_slug(obj.name)


class CatalogTeamWriteSerializer(serializers.ModelSerializer):
    country_id = serializers.IntegerField(required=False)
    league_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Team
        fields = ['name', 'country_id', 'league_id', 'logo', 'is_verified']
        extra_kwargs = {
            'name': {'validators': []},
        }

    def validate_name(self, value):
        cleaned = ' '.join((value or '').strip().split())
        if not cleaned:
            raise serializers.ValidationError('Team name is required.')
        return cleaned

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, 'instance', None)
        is_verified = attrs.get('is_verified', instance.is_verified if instance is not None else True)
        country_id = attrs.get('country_id', instance.country_id if instance is not None else None)
        league_id = attrs.get('league_id', instance.league_id if instance is not None else None)

        country = None
        if country_id not in (None, ''):
            country = Country.objects.filter(pk=country_id).first()
            if country is None:
                raise serializers.ValidationError({'country_id': 'Country is invalid.'})
            country_changed = instance is None or country.id != instance.country_id
            if country_changed and not country.is_active:
                raise serializers.ValidationError({'country_id': 'Country must be active.'})
        elif is_verified:
            raise serializers.ValidationError({'country_id': 'Country is required for verified teams.'})

        league = None
        if league_id not in (None, ''):
            league = League.objects.select_related('country').filter(pk=league_id).first()
            if league is None:
                raise serializers.ValidationError({'league_id': 'League is invalid.'})
            league_changed = instance is None or league.id != instance.league_id
            if league_changed and not league.is_active:
                raise serializers.ValidationError({'league_id': 'League must be active.'})
            if country is None:
                raise serializers.ValidationError({'country_id': 'Country is required when setting a league.'})
            if league.country_id != country.id:
                raise serializers.ValidationError({
                    'detail': 'Selected league does not belong to the selected country.',
                    'code': 'league_country_mismatch',
                })

        attrs['country'] = country
        attrs['league'] = league
        return attrs


class TeamModerationApproveSerializer(serializers.Serializer):
    name = serializers.CharField()
    country_id = serializers.IntegerField()
    league_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_name(self, value):
        cleaned = ' '.join((value or '').strip().split())
        if not cleaned:
            raise serializers.ValidationError('Team name is required.')
        return cleaned

    def validate(self, attrs):
        country = Country.objects.filter(
            pk=attrs['country_id'],
            is_active=True,
        ).first()
        if country is None:
            raise serializers.ValidationError({'country_id': 'Country must be an active country.'})

        league_id = attrs.get('league_id', serializers.empty)
        league = None
        if league_id not in (serializers.empty, None):
            league = League.objects.select_related('country').filter(pk=league_id).first()
            if league is None:
                raise serializers.ValidationError({'league_id': 'League is invalid.'})
            if not league.is_active:
                raise serializers.ValidationError({'league_id': 'League must be active.'})

        attrs['country'] = country
        attrs['league'] = league
        return attrs


class TeamModerationDeleteContentSerializer(serializers.Serializer):
    REASON_SPAM = 'spam'
    REASON_OFFENSIVE_NAME = 'offensive_name'
    REASON_INVALID_TEAM = 'invalid_team'
    REASON_DUPLICATE_ABUSE = 'duplicate_abuse'
    REASON_OTHER = 'other'
    REASON_CHOICES = {
        REASON_SPAM,
        REASON_OFFENSIVE_NAME,
        REASON_INVALID_TEAM,
        REASON_DUPLICATE_ABUSE,
        REASON_OTHER,
    }

    confirmation = serializers.CharField(allow_blank=True)
    reason = serializers.CharField()
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_confirmation(self, value):
        return (value or '').strip()

    def validate_reason(self, value):
        cleaned = (value or '').strip()
        if cleaned not in self.REASON_CHOICES:
            raise serializers.ValidationError('Reason is invalid.')
        return cleaned

    def validate_note(self, value):
        return (value or '').strip()


class TeamModerationActionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)
    undone_by_username = serializers.CharField(source='undone_by.username', read_only=True)

    class Meta:
        model = TeamModerationAction
        fields = [
            'id',
            'action_type',
            'actor_username',
            'source_team_id_snapshot',
            'source_team_name',
            'target_team_name',
            'summary',
            'is_reversible',
            'undo_block_reason',
            'created_at',
            'undone_at',
            'undone_by_username',
        ]


class KitTypeModerationActionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)
    undone_by_username = serializers.CharField(source='undone_by.username', read_only=True)
    summary = serializers.SerializerMethodField()
    can_undo = serializers.SerializerMethodField()

    class Meta:
        model = KitTypeModerationAction
        fields = [
            'id',
            'action_type',
            'actor_username',
            'created_at',
            'undone_at',
            'undone_by_username',
            'is_reversible',
            'undo_block_reason',
            'team_name',
            'season',
            'source_kit_type_name',
            'target_kit_type_name',
            'summary',
            'can_undo',
        ]

    def get_summary(self, obj):
        if obj.action_type == KitTypeModerationAction.ACTION_APPROVE:
            return f'Approved {obj.source_kit_type_name} for {obj.team_name} {obj.season}'.strip()
        if obj.action_type == KitTypeModerationAction.ACTION_REJECT:
            return f'Rejected {obj.source_kit_type_name} for {obj.team_name} {obj.season}'.strip()
        if obj.action_type == KitTypeModerationAction.ACTION_MERGE:
            return f'Merged {obj.source_kit_type_name} into {obj.target_kit_type_name}'.strip()
        return obj.action_type

    def get_can_undo(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        permission_check = self.context.get('can_undo_moderation_action', can_undo_moderation_action)
        state_check = self.context.get(
            'moderation_action_is_currently_undoable',
            moderation_action_is_currently_undoable,
        )

        if not permission_check(request.user, obj):
            return False

        can_undo, _reason = state_check(obj)
        return bool(can_undo)


class ApprovedTeamSeasonKitTypeSerializer(serializers.ModelSerializer):
    team_id = serializers.IntegerField(source='team.id', read_only=True)
    kit_type_id = serializers.IntegerField(source='kit_type.id', read_only=True)
    kit_type_name = serializers.CharField(source='kit_type.name', read_only=True)
    kit_type_slug = serializers.CharField(source='kit_type.slug', read_only=True)
    default_visibility = serializers.CharField(source='kit_type.default_visibility', read_only=True)
    sort_order = serializers.IntegerField(source='kit_type.sort_order', read_only=True)

    class Meta:
        model = TeamSeasonKitType
        fields = [
            'id',
            'team_id',
            'season',
            'kit_type_id',
            'kit_type_name',
            'kit_type_slug',
            'default_visibility',
            'sort_order',
        ]


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
    can_view_kit_values = serializers.SerializerMethodField()

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
            'kit', 'images', 'condition_display', 'technology_display', 'shirt_version_id', 'shirt_version_code', 'shirt_version_display', 'shirt_version_manual_value_recommended', 'shirt_version_valuation_note', 'final_value', 'size_display', 'added_at', 'is_owner', 'owner_id', 'owner_username', 'owner_avatar', 'can_view_kit_values', 'is_hidden_by_moderation',
            # Write-only fields
            'team_name', 'season', 'kit_type', 'kit_type_id', 'kit_type_slug', 'new_images', 'deleted_images', 'images_order',
            # Modifiable fields
            'condition', 'shirt_technology', 'size', 'for_sale', 'manual_value', 'likes_count', 'comments_count', 'is_liked', 'valuation_warning', 'player_name', 'player_number', 'private_note', 'offer_link', 'in_the_collection', 'has_private_note'
        ]
        read_only_fields = ['user', 'final_value', 'kit', 'images', 'condition_display', 'technology_display', 'shirt_version_id', 'shirt_version_code', 'shirt_version_display', 'shirt_version_manual_value_recommended', 'shirt_version_valuation_note', 'size_display', 'added_at', 'is_owner', 'owner_id', 'owner_username', 'owner_avatar', 'can_view_kit_values', 'is_hidden_by_moderation', 'likes_count', 'comments_count', 'is_liked', 'valuation_warning', 'has_private_note']
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

    def get_can_view_kit_values(self, obj):
        request = self.context.get('request')
        return can_view_collection_value(getattr(request, 'user', None), obj.user)

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

        if not self.get_can_view_kit_values(instance):
            representation['final_value'] = None
            representation['manual_value'] = None
            kit_data = representation.get('kit')
            if isinstance(kit_data, dict):
                kit_data['estimated_price'] = None

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

        if kit_type_ref is None:
            kit_type_ref = get_or_create_pending_kit_type(
                legacy_name=kit_type,
                created_by=validated_data.get('user'),
            )
            if kit_type_ref is not None:
                kit_type = kit_type_ref.name

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
        ensure_team_season_suggestion(
            team=team,
            season=season,
            kit_type=kit_type_ref,
            created_by=user_kit.user,
        )

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

            if kit_type_ref is None:
                kit_type_ref = get_or_create_pending_kit_type(
                    legacy_name=kit_type,
                    created_by=instance.user,
                )
                if kit_type_ref is not None:
                    kit_type = kit_type_ref.name

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
            ensure_team_season_suggestion(
                team=team,
                season=season,
                kit_type=kit_type_ref,
                created_by=instance.user,
            )

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
            'show_collection_value_publicly',
            
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
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'is_superuser', 'profile']

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
    total_value = serializers.SerializerMethodField()
    can_view_collection_value = serializers.SerializerMethodField()

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
    show_collection_value_publicly = serializers.BooleanField(
        source='profile.show_collection_value_publicly',
        read_only=True,
    )

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

    def _is_owner(self, obj):
        request = self.context.get('request')
        return bool(
            request
            and request.user.is_authenticated
            and request.user == obj
        )

    def get_can_view_collection_value(self, obj):
        request = self.context.get('request')
        return can_view_collection_value(getattr(request, 'user', None), obj)

    def get_total_value(self, obj):
        if not self.get_can_view_collection_value(obj):
            return None
        return getattr(obj, 'total_value', None)

    class Meta:
        model = User
        fields = [
            'username', 'date_joined',
            'total_kits', 'total_value',
            'can_view_collection_value',
            'show_collection_value_publicly',

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
