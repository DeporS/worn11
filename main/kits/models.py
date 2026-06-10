from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q, Sum, Count
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify

SHIRT_TECHNOLOGIES = [
    ('PLAYER_ISSUE', 'Player Issue'),
    ('REPLICA', 'Replica'),
    ('MATCH_WORN', 'Match Worn'),
]

SHIRT_TYPES = [
    ('Home', 'Home'),
    ('Away', 'Away'),
    ('Third', 'Third'),
    ('Fourth', 'Fourth'),
    ('Cup', 'Cup'),
    ('Training', 'Training'),
    ('GK', 'Goalkeeper'),
    ('Special', 'Special Edition'),
]

SIZE_CHOICES = [
    ('KIDS', 'Kids'),
    ('XS', 'Extra Small (XS)'),
    ('S', 'Small (S)'),
    ('M', 'Medium (M)'),
    ('L', 'Large (L)'),
    ('XL', 'Extra Large (XL)'),
    ('XXL', 'Double Extra Large (XXL)'),
    ('XXXL', 'Triple Extra Large (XXXL)'),
]

CONDITION_CHOICES = [
    ('BNWT', 'Brand New With Tags'),
    ('MINT', 'New Without Tags'),
    ('VERY_GOOD', 'Very Good Condition'),
    ('GOOD', 'Good Condition'),
    ('FAIR', 'Fair Condition'),
    ('POOR', 'Poor Condition'),
]

SIZE_MULTIPLIERS = {
    'KIDS': Decimal('0.25'),
    'XS': Decimal('0.4'),
    'S': Decimal('0.6'),
    'M': Decimal('0.9'),
    'L': Decimal('1.0'),
    'XL': Decimal('0.9'),
    'XXL': Decimal('0.75'),
    'XXXL': Decimal('0.6'),
}

CONDITION_MULTIPLIERS = {
    'BNWT': Decimal('2.0'),
    'MINT': Decimal('1.5'),
    'VERY_GOOD': Decimal('1.0'),
    'GOOD': Decimal('0.85'),
    'FAIR': Decimal('0.7'),
    'POOR': Decimal('0.5'),
}

TECHNOLOGIE_MULTIPLIERS = {
    'PLAYER_ISSUE': Decimal('1.5'),
    'REPLICA': Decimal('1.0'),
    'MATCH_WORN': Decimal('5.0'),
}

CURRENCY_CHOICES = [
    ('USD', 'US Dollar (USD)'),
    ('EUR', 'Euro (EUR)'),
    ('GBP', 'British Pound (GBP)'),
]

KIT_REPORT_REASON_CHOICES = [
    ('wrong_team', 'Wrong team'),
    ('wrong_season', 'Wrong season'),
    ('wrong_kit_type', 'Wrong kit type'),
    ('wrong_details', 'Wrong details'),
    ('fake_or_misleading', 'Fake or misleading'),
    ('prohibited_content', 'Prohibited content'),
    ('spam', 'Spam'),
    ('harassment_or_abuse', 'Harassment or abuse'),
    ('other', 'Other'),
]

KIT_REPORT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('reviewed', 'Reviewed'),
    ('dismissed', 'Dismissed'),
    ('resolved', 'Resolved'),
]

NOTIFICATION_TYPE_CHOICES = [
    ('kit_like', 'Kit like'),
    ('follow', 'Follow'),
    ('kit_comment', 'Kit comment'),
    ('comment_like', 'Comment like'),
    ('comment_reply', 'Comment reply'),
]

AUTOMATED_VALUATION_UNAVAILABLE_MESSAGE = (
    "Automated valuation is not available for this kit yet, so its value will be set to 0."
)

CANONICAL_WISHLIST_KIT_TYPES = [
    'Home',
    'Away',
    'Third',
    'Fourth',
    'Cup',
    'Training',
    'Goalkeeper',
    'Special',
]

WISHLIST_KIT_TYPE_ALIASES = {
    'home': 'Home',
    'away': 'Away',
    'third': 'Third',
    'fourth': 'Fourth',
    'cup': 'Cup',
    'training': 'Training',
    'gk': 'Goalkeeper',
    'goalkeeper': 'Goalkeeper',
    'keeper': 'Goalkeeper',
    'goalie': 'Goalkeeper',
    'special': 'Special',
    'special edition': 'Special',
}


def build_team_slug(team_name):
    return slugify(team_name or "")


def normalize_wishlist_kit_type(kit_type):
    cleaned = ' '.join((kit_type or '').strip().split())
    if not cleaned:
        return ''

    lowered = cleaned.lower()
    if lowered in WISHLIST_KIT_TYPE_ALIASES:
        return WISHLIST_KIT_TYPE_ALIASES[lowered]

    if lowered.startswith('special'):
        return 'Special'

    for canonical_type in CANONICAL_WISHLIST_KIT_TYPES:
        if canonical_type.lower() == lowered:
            return canonical_type

    return cleaned

# User profile
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Status fields
    is_pro = models.BooleanField(default=False)  # Pro users have extra features
    is_moderator = models.BooleanField(default=False)  # Moderators can help manage content
    has_changed_username = models.BooleanField(default=False)
    on_vacation = models.BooleanField(default=False)

    # pro_expiration_date = models.DateTimeField(null=True, blank=True)

    # Personal info
    avatar = models.ImageField(upload_to='profile_avatars/', null=True, blank=True)
    bio = models.TextField(max_length=1000, blank=True)
    name = models.CharField(max_length=150, blank=True)
    surname = models.CharField(max_length=150, blank=True)

    # Preferences and location
    country = models.ForeignKey('Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    favorite_team = models.ForeignKey('Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='fans')
    preferred_size = models.CharField(max_length=10, choices=SIZE_CHOICES, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')

    # Contact 
    contact_email = models.EmailField(max_length=254, blank=True, null=True)

    # Social links
    facebook_link = models.URLField(max_length=2048, null=True, blank=True)
    instagram_link = models.URLField(max_length=2048, null=True, blank=True)
    twitter_link = models.URLField(max_length=2048, null=True, blank=True)
    youTube_link = models.URLField(max_length=2048, null=True, blank=True)
    tiktok_link = models.URLField(max_length=2048, null=True, blank=True)
    
    # Marketplaces
    vinted_link = models.URLField(max_length=2048, null=True, blank=True)
    ebay_link = models.URLField(max_length=2048, null=True, blank=True)
    depop_link = models.URLField(max_length=2048, null=True, blank=True)
    website_link = models.URLField(max_length=2048, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"

# Following system
class Follow(models.Model):
    follower = models.ForeignKey(
        User,
        related_name='following',
        on_delete=models.CASCADE
    )
    following = models.ForeignKey(
        User,
        related_name='followers',
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        indexes = [
            models.Index(fields=['follower', 'following']),
        ]
    
    def clean(self):
        if self.follower == self.following:
            raise ValidationError("You cannot follow yourself.")    

    def save(self, *args, **kwargs):
        self.full_clean()  # This will call the clean method to validate before saving
        super().save(*args, **kwargs)    

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"

# Countries Model
class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    flag = models.ImageField(upload_to='country_flags/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_countries',
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name_plural = "Countries"
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                name='kits_country_name_ci_unique',
            ),
        ]

    def __str__(self):
        return self.name

# League Model (ex. Premier League, La Liga, etc.)
class League(models.Model):
    name = models.CharField(max_length=100, unique=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name='leagues')
    logo = models.ImageField(upload_to='league_logos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_leagues',
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    hex_color = models.CharField(max_length=7, default="#333333", help_text="Hex color code for the league (e.g., #FF0000)")
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.country.name if self.country else 'No Country'})"


# Football Teams (ex. Barcelona, Real Madrid, etc.)
class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to='team_logos/', null=True, blank=True)

    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name='teams')
    league = models.ForeignKey(League, on_delete=models.SET_NULL, null=True, blank=True, related_name='teams')

    is_verified = models.BooleanField(default=False) # Admin can verify teams to avoid duplicates

    def __str__(self):
        return self.name


class KitType(models.Model):
    CATEGORY_OUTFIELD = 'outfield'
    CATEGORY_GOALKEEPER = 'goalkeeper'
    CATEGORY_TRAINING = 'training'
    CATEGORY_SPECIAL = 'special'
    CATEGORY_COMPETITION = 'competition'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_OUTFIELD, 'Outfield'),
        (CATEGORY_GOALKEEPER, 'Goalkeeper'),
        (CATEGORY_TRAINING, 'Training'),
        (CATEGORY_SPECIAL, 'Special'),
        (CATEGORY_COMPETITION, 'Competition'),
        (CATEGORY_OTHER, 'Other'),
    ]

    STATUS_APPROVED = 'approved'
    STATUS_PENDING = 'pending'
    STATUS_REJECTED = 'rejected'
    STATUS_MERGED = 'merged'
    STATUS_CHOICES = [
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_MERGED, 'Merged'),
    ]

    VISIBILITY_PRIMARY = 'primary'
    VISIBILITY_EXPANDED = 'expanded'
    VISIBILITY_NONE = 'none'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIMARY, 'Primary'),
        (VISIBILITY_EXPANDED, 'Expanded'),
        (VISIBILITY_NONE, 'None'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    canonical_code = models.CharField(max_length=64, unique=True, null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    default_visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_NONE,
    )
    sort_order = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_kit_types',
    )
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_kit_types',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    merged_into = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='merged_types',
    )

    class Meta:
        ordering = ['sort_order', 'name', 'id']

    def __str__(self):
        return self.name


class KitTypeAlias(models.Model):
    alias_normalized = models.CharField(max_length=120, unique=True)
    kit_type = models.ForeignKey(KitType, on_delete=models.CASCADE, related_name='aliases')
    display_alias = models.CharField(max_length=120, blank=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_kit_type_aliases',
    )
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_kit_type_aliases',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['alias_normalized', 'id']

    def __str__(self):
        return f'{self.alias_normalized} -> {self.kit_type.name}'


class ShirtVersion(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    valuation_multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal('1.000'),
    )
    manual_value_recommended = models.BooleanField(default=False)
    valuation_note = models.TextField(blank=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name', 'id']

    def __str__(self):
        return self.name


class TeamSeasonKitType(models.Model):
    STATUS_APPROVED = 'approved'
    STATUS_PENDING = 'pending'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    SOURCE_SYSTEM_DEFAULT = 'system_default'
    SOURCE_UPLOAD = 'upload'
    SOURCE_MODERATOR = 'moderator'
    SOURCE_CHOICES = [
        (SOURCE_SYSTEM_DEFAULT, 'System default'),
        (SOURCE_UPLOAD, 'Upload'),
        (SOURCE_MODERATOR, 'Moderator'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='season_kit_types')
    season = models.CharField(max_length=20)
    kit_type = models.ForeignKey(KitType, on_delete=models.CASCADE, related_name='team_seasons')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_UPLOAD)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_team_season_kit_types',
    )
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_team_season_kit_types',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['team__name', '-season', 'kit_type__sort_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['team', 'season', 'kit_type'],
                name='unique_team_season_kit_type',
            ),
        ]

    def __str__(self):
        return f'{self.team.name} {self.season} {self.kit_type.name}'


class KitTypeModerationAction(models.Model):
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_MERGE = 'merge'
    ACTION_CHOICES = [
        (ACTION_APPROVE, 'Approve'),
        (ACTION_REJECT, 'Reject'),
        (ACTION_MERGE, 'Merge'),
    ]

    actor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='kit_type_moderation_actions',
    )
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    team_season_kit_type = models.ForeignKey(
        TeamSeasonKitType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='moderation_actions',
    )
    source_kit_type = models.ForeignKey(
        KitType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='source_moderation_actions',
    )
    target_kit_type = models.ForeignKey(
        KitType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='target_moderation_actions',
    )
    team_name = models.CharField(max_length=100, blank=True, default='')
    season = models.CharField(max_length=20, blank=True, default='')
    source_kit_type_name = models.CharField(max_length=120, blank=True, default='')
    target_kit_type_name = models.CharField(max_length=120, blank=True, default='')
    previous_state = models.JSONField(default=dict, blank=True)
    resulting_state = models.JSONField(default=dict, blank=True)
    is_reversible = models.BooleanField(default=True)
    undo_block_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    undone_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='undone_kit_type_moderation_actions',
    )

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['created_at', 'id']),
            models.Index(fields=['action_type', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_action_type_display()} by {self.actor.username} at {self.created_at}'


class TeamModerationAction(models.Model):
    ACTION_APPROVE = 'approve'
    ACTION_MERGE = 'merge'
    ACTION_REJECT = 'reject'
    ACTION_DELETE_CONTENT = 'delete_content'
    ACTION_CHOICES = [
        (ACTION_APPROVE, 'Approve'),
        (ACTION_MERGE, 'Merge'),
        (ACTION_REJECT, 'Reject'),
        (ACTION_DELETE_CONTENT, 'Delete content'),
    ]

    actor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='team_moderation_actions',
    )
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    source_team_id_snapshot = models.IntegerField(null=True, blank=True)
    source_team_name = models.CharField(max_length=100, blank=True, default='')
    target_team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='team_moderation_actions',
    )
    target_team_name = models.CharField(max_length=100, blank=True, default='')
    previous_state = models.JSONField(default=dict, blank=True)
    resulting_state = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    is_reversible = models.BooleanField(default=False)
    undo_block_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    undone_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='undone_team_moderation_actions',
    )

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['created_at', 'id']),
            models.Index(fields=['action_type', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_action_type_display()} team action by {self.actor.username} at {self.created_at}'


# Football Kits (ex. Arsenal Home 2021/2022)
class Kit(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='kits')
    season = models.CharField(max_length=20, help_text="e.g., 2021/2022") # e.g., "2021/2022"
    kit_type = models.CharField(max_length=50, help_text="e.g., Home, Away, Third") # e.g., "Home", "Away", "Third"
    kit_type_ref = models.ForeignKey(
        KitType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='kits',
    )

    # Simple pricing
    estimated_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Estimated price in $ (Size L in Very Good condition)")
    
    # Only one image for context
    main_image = models.ImageField(upload_to='kit_images/', null=True, blank=True)

    def __str__(self):
        return f"{self.team.name} {self.kit_type} {self.season}"

# Users' Football Kits
class UserKit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collection')
    kit = models.ForeignKey(Kit, on_delete=models.CASCADE, related_name='owned_by')
    shirt_technology = models.CharField(max_length=20, choices=SHIRT_TECHNOLOGIES)
    shirt_version = models.ForeignKey(
        ShirtVersion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='user_kits',
    )
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    size = models.CharField(max_length=10, choices=SIZE_CHOICES)
    player_name = models.CharField(max_length=100, null=True, blank=True)
    player_number = models.CharField(max_length=10, null=True, blank=True)
    private_note = models.TextField(blank=True, default='')
    for_sale = models.BooleanField(default=False)
    offer_link = models.URLField(max_length=2048, null=True, blank=True)

    # If false, it means the user had it but sold or traded it away
    in_the_collection = models.BooleanField(default=True)  

    # How many users like this kit
    likes = models.ManyToManyField(User, related_name='liked_kits', blank=True)

    def total_likes(self):
        return self.likes.count()

    # When was added to the collection
    added_at = models.DateTimeField(auto_now_add=True)

    # Value fields
    manual_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Set your own value for the kit. If empty, the system will calculate it automatically."
    )

    final_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Final value of the kit, either manual or calculated."
    )

    def is_automated_valuation_available(self):
        base_price = getattr(self.kit, 'estimated_price', None)
        return base_price is not None and base_price > 0

    def get_valuation_warning(self):
        if self.manual_value:
            return None

        if not self.is_automated_valuation_available():
            return AUTOMATED_VALUATION_UNAVAILABLE_MESSAGE

        return None

    def save(self, *args, **kwargs):
        # Calculate final value if manual_value is not set
        if self.manual_value:
            # If user set a manual value, use it
            self.final_value = self.manual_value
        else:
            # Calculate based on multipliers
            base_price = getattr(self.kit, 'estimated_price', None)

            if base_price is not None and base_price > 0:
                size_multiplier = SIZE_MULTIPLIERS.get(self.size, Decimal('1.0'))
                condition_multiplier = CONDITION_MULTIPLIERS.get(self.condition, Decimal('1.0'))
                if self.shirt_version_id:
                    technology_multiplier = self.shirt_version.valuation_multiplier
                else:
                    technology_multiplier = TECHNOLOGIE_MULTIPLIERS.get(
                        self.shirt_technology,
                        Decimal('1.0'),
                    )

                calculated_value = base_price * size_multiplier * condition_multiplier * technology_multiplier
                self.final_value = calculated_value.quantize(Decimal('0.01'))  # Round to 2 decimal places
            else:
                self.final_value = Decimal('0.00')
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username}'s {self.kit} ({self.size}, {self.condition})"


def calculate_collection_total_value(user):
    stats = UserKit.objects.filter(
        user=user,
        in_the_collection=True,
    ).aggregate(
        total_value=Sum('final_value'),
        kits_count=Count('id'),
    )
    return (
        stats['total_value'] or Decimal('0.00'),
        stats['kits_count'] or 0,
    )


class CollectionValueSnapshot(models.Model):
    REASON_INITIAL = 'initial'
    REASON_KIT_ADDED = 'kit_added'
    REASON_KIT_REMOVED = 'kit_removed'
    REASON_KIT_UPDATED = 'kit_updated'
    REASON_VALUE_UPDATED = 'value_updated'
    REASON_COLLECTION_STATUS_CHANGED = 'collection_status_changed'
    REASON_BACKFILL = 'backfill'

    REASON_CHOICES = [
        (REASON_INITIAL, 'Initial'),
        (REASON_KIT_ADDED, 'Kit added'),
        (REASON_KIT_REMOVED, 'Kit removed'),
        (REASON_KIT_UPDATED, 'Kit updated'),
        (REASON_VALUE_UPDATED, 'Value updated'),
        (REASON_COLLECTION_STATUS_CHANGED, 'Collection status changed'),
        (REASON_BACKFILL, 'Backfill'),
    ]

    user = models.ForeignKey(
        User,
        related_name='collection_value_snapshots',
        on_delete=models.CASCADE,
    )
    total_value = models.DecimalField(max_digits=12, decimal_places=2)
    kits_count = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=64, choices=REASON_CHOICES)
    related_userkit = models.ForeignKey(
        UserKit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'id']),
        ]

    def __str__(self):
        return f'{self.user.username} {self.total_value} ({self.reason})'


def record_collection_value_snapshot(user, reason, related_userkit=None):
    total_value, kits_count = calculate_collection_total_value(user)
    return CollectionValueSnapshot.objects.create(
        user=user,
        total_value=total_value,
        kits_count=kits_count,
        reason=reason,
        related_userkit=related_userkit,
    )


class WishlistItem(models.Model):
    user = models.ForeignKey(User, related_name='wishlist_items', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='wishlist_items')
    season = models.CharField(max_length=20)
    kit_type = models.CharField(max_length=32)
    kit_type_ref = models.ForeignKey(
        KitType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='wishlist_items',
    )
    source_userkit = models.ForeignKey(
        UserKit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='wishlist_references',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'team', 'season', 'kit_type'],
                name='unique_user_wishlist_variant',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['team', 'season', 'kit_type']),
        ]

    def save(self, *args, **kwargs):
        self.kit_type = normalize_wishlist_kit_type(self.kit_type)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.username} wants {self.team.name} {self.season} {self.kit_type}'


class KitComment(models.Model):
    kit = models.ForeignKey(UserKit, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kit_comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, related_name='replies', null=True, blank=True)
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='direct_replies',
        null=True,
        blank=True,
    )
    body = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def clean(self):
        self.body = (self.body or '').strip()

        if not self.body:
            raise ValidationError({'body': 'Comment cannot be empty.'})

        if self.parent_id is None:
            self.reply_to = None
            return

        thread_root = self.parent.parent if self.parent.parent_id is not None else self.parent
        if thread_root.kit_id != self.kit_id:
            raise ValidationError({'parent': 'Reply must belong to the same kit.'})

        if thread_root.parent_id is not None:
            raise ValidationError({'parent': 'Parent must be a top-level comment.'})

        self.parent = thread_root

        if self.reply_to_id is None:
            self.reply_to = thread_root
        else:
            if self.reply_to.kit_id != self.kit_id:
                raise ValidationError({'reply_to': 'Reply target must belong to the same kit.'})

            if self.reply_to_id == self.id:
                raise ValidationError({'reply_to': 'Reply target cannot be the comment itself.'})

            if self.reply_to.parent_id is None:
                if self.reply_to_id != thread_root.id:
                    raise ValidationError({'reply_to': 'Top-level reply target must match the thread root.'})
            elif self.reply_to.parent_id != thread_root.id:
                raise ValidationError({'reply_to': 'Reply target must belong to the same thread.'})

        if self.parent:
            if self.parent.kit_id != self.kit_id:
                raise ValidationError({'parent': 'Reply must belong to the same kit.'})

    def save(self, *args, **kwargs):
        self.body = (self.body or '').strip()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Comment by {self.user.username} on kit {self.kit_id}'


class KitCommentLike(models.Model):
    comment = models.ForeignKey(KitComment, on_delete=models.CASCADE, related_name='comment_likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='liked_kit_comments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(fields=['comment', 'user'], name='unique_comment_like')
        ]

    def __str__(self):
        return f'{self.user.username} liked comment {self.comment_id}'


class KitReport(models.Model):
    kit = models.ForeignKey(UserKit, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kit_reports')
    reason = models.CharField(max_length=50, choices=KIT_REPORT_REASON_CHOICES)
    description = models.TextField(max_length=1000, blank=True)
    status = models.CharField(max_length=20, choices=KIT_REPORT_STATUS_CHOICES, default='pending')
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_kit_reports',
    )
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['kit', 'reporter'], name='unique_kit_report_per_user')
        ]

    def clean(self):
        self.description = (self.description or '').strip()
        self.resolution_note = (self.resolution_note or '').strip()

        if self.reason == 'other' and not self.description:
            raise ValidationError({'description': 'Description is required when selecting Other.'})

    def save(self, *args, **kwargs):
        self.description = (self.description or '').strip()
        self.resolution_note = (self.resolution_note or '').strip()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.reporter.username} reported kit {self.kit_id} ({self.reason})'


class Conversation(models.Model):
    participant_one = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='started_conversations',
    )
    participant_two = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['participant_one', 'participant_two'],
                name='unique_conversation_pair',
            )
        ]

    @staticmethod
    def normalize_participants(user_a, user_b):
        if user_a.id <= user_b.id:
            return user_a, user_b
        return user_b, user_a

    @classmethod
    def get_or_create_between(cls, user_a, user_b):
        first_user, second_user = cls.normalize_participants(user_a, user_b)
        conversation, _ = cls.objects.get_or_create(
            participant_one=first_user,
            participant_two=second_user,
        )
        return conversation

    def clean(self):
        if self.participant_one_id and self.participant_two_id:
            if self.participant_one_id == self.participant_two_id:
                raise ValidationError("You cannot create a conversation with yourself.")

            if self.participant_one_id > self.participant_two_id:
                self.participant_one, self.participant_two = self.normalize_participants(
                    self.participant_one,
                    self.participant_two,
                )

    def save(self, *args, **kwargs):
        if self.participant_one_id and self.participant_two_id:
            self.participant_one, self.participant_two = self.normalize_participants(
                self.participant_one,
                self.participant_two,
            )
        self.full_clean()
        return super().save(*args, **kwargs)

    def includes_user(self, user):
        return user.id in {self.participant_one_id, self.participant_two_id}

    def get_other_participant(self, user):
        if user.id == self.participant_one_id:
            return self.participant_two
        if user.id == self.participant_two_id:
            return self.participant_one
        return None

    def __str__(self):
        return f'{self.participant_one.username} / {self.participant_two.username}'


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def clean(self):
        self.body = (self.body or '').strip()

        if not self.body:
            raise ValidationError({'body': 'Message cannot be empty.'})

        if self.conversation_id and self.sender_id and not self.conversation.includes_user(self.sender):
            raise ValidationError({'sender': 'Sender must be a participant in the conversation.'})

    def save(self, *args, **kwargs):
        self.body = (self.body or '').strip()
        self.full_clean()
        result = super().save(*args, **kwargs)
        Conversation.objects.filter(pk=self.conversation_id).update(updated_at=timezone.now())
        return result

    def __str__(self):
        return f'Message {self.id} in conversation {self.conversation_id}'


class Notification(models.Model):
    recipient = models.ForeignKey(
        User,
        related_name='notifications',
        on_delete=models.CASCADE,
    )
    actor = models.ForeignKey(
        User,
        related_name='notifications_sent',
        on_delete=models.CASCADE,
    )
    type = models.CharField(max_length=32, choices=NOTIFICATION_TYPE_CHOICES)
    kit = models.ForeignKey(
        UserKit,
        null=True,
        blank=True,
        related_name='notifications',
        on_delete=models.CASCADE,
    )
    comment = models.ForeignKey(
        KitComment,
        null=True,
        blank=True,
        related_name='notifications',
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['recipient', 'read_at', '-created_at', '-id']),
            models.Index(fields=['recipient', 'type', '-created_at', '-id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'type', 'kit'],
                condition=Q(type='kit_like', kit__isnull=False),
                name='unique_kit_like_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'type'],
                condition=Q(type='follow', kit__isnull=True),
                name='unique_follow_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'type', 'comment'],
                condition=Q(
                    type__in=['kit_comment', 'comment_like', 'comment_reply'],
                    comment__isnull=False,
                ),
                name='unique_comment_notification',
            ),
        ]

    def __str__(self):
        return f'{self.actor.username} -> {self.recipient.username} ({self.type})'


# Kit Images (multiple images per kit)
class UserKitImage(models.Model):
    user_kit = models.ForeignKey(UserKit, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='user_kits/')
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']  
    
    def __str__(self):
        return f"Image for {self.user_kit}"



# SIGNALS

# Create or update user profile on User creation
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except ObjectDoesNotExist:
        # Create profile if it does not exist
        Profile.objects.create(user=instance)
