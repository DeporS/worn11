from django.contrib import admin
from django.db.models import Count
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import (
    Conversation,
    Country,
    Kit,
    KitReport,
    KitType,
    KitTypeAlias,
    League,
    Message,
    Profile,
    ShirtVersion,
    Team,
    TeamSeasonKitType,
    UserKit,
    UserKitImage,
)

class UserKitImageInline(admin.TabularInline):
    model = UserKitImage
    extra = 1 # Number of extra forms to display

class UserKitAdmin(admin.ModelAdmin):
    list_display = ('user', 'kit', 'size', 'condition', 'shirt_technology', 'final_value', 'for_sale', 'added_at')
    list_filter = ('size', 'condition', 'shirt_technology', 'for_sale', 'added_at')
    search_fields = ('user__username', 'kit__team__name', 'kit__season', 'kit__kit_type')

    readonly_fields = ('final_value', 'added_at')

    inlines = [UserKitImageInline] # Include the inline images

class KitAdmin(admin.ModelAdmin):
    list_display = ('team', 'season', 'kit_type', 'estimated_price')
    list_filter = ('season', 'kit_type', 'team__is_verified')
    search_fields = ('team__name', 'season', 'kit_type')


class KitTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'canonical_code', 'category', 'status', 'default_visibility', 'sort_order')
    list_filter = ('category', 'status', 'default_visibility')
    search_fields = ('name', 'slug', 'canonical_code')


class KitTypeAliasAdmin(admin.ModelAdmin):
    list_display = ('alias_normalized', 'kit_type', 'display_alias', 'created_at')
    search_fields = ('alias_normalized', 'display_alias', 'kit_type__name')


class TeamSeasonKitTypeAdmin(admin.ModelAdmin):
    list_display = ('team', 'season', 'kit_type', 'status', 'source', 'created_at')
    list_filter = ('status', 'source', 'season')
    search_fields = ('team__name', 'season', 'kit_type__name')


class ShirtVersionAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'valuation_multiplier',
        'manual_value_recommended',
        'is_active',
        'sort_order',
    )
    list_filter = ('manual_value_recommended', 'is_active')
    search_fields = ('code', 'name', 'description')


# Register in admin
class TeamAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'country', 'league', 'kits_in_collections_count', 'kits_definitions_count', 'is_verified']

    list_filter = ['is_verified', 'country', 'league']

    search_fields = ['name', 'country__name', 'league__name']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Annotate adds virtual columns to the SQL query
        queryset = queryset.annotate(
            # Count how many kits of this team are owned by users (All user kits with this team)
            _user_kits_count=Count('kits__owned_by', distinct=True),
            
            # how many kit definitions of this team are in the database (Distinct team kits, f.e. different seasons/types)
            _definitions_count=Count('kits', distinct=True)
        )
        return queryset
    
    # Method to display the number of kits in user collections
    @admin.display(description='In User Collections', ordering='_user_kits_count')
    def kits_in_collections_count(self, obj):
        return obj._user_kits_count

    # Method to display the number of kit definitions 
    @admin.display(description='Kit Definitions (DB)', ordering='_definitions_count')
    def kits_definitions_count(self, obj):
        return obj._definitions_count

# User Profile Inline
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile INFO (Pro & Moderator Status)'

# Custom User Admin to include Profile
class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline, )

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_is_pro', 'get_is_moderator')

    list_filter = UserAdmin.list_filter + ('is_active', 'profile__is_pro', 'profile__is_moderator')


    # Methods to display is_pro and is_moderator in list_display
    def get_is_pro(self, obj):
        return getattr(obj.profile, 'is_pro', False)
    
    get_is_pro.short_description = 'Is Pro'
    get_is_pro.boolean = True

    def get_is_moderator(self, obj):
        return getattr(obj.profile, 'is_moderator', False)
    
    get_is_moderator.short_description = 'Is Moderator'
    get_is_moderator.boolean = True

# Country Admin
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('is_active',)

# League Admin
class LeagueAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'is_active', 'order')
    list_filter = ('country', 'is_active')
    search_fields = ('name', 'country__name')


class KitReportAdmin(admin.ModelAdmin):
    list_display = ('kit', 'reporter', 'reason', 'status', 'created_at')
    list_filter = ('reason', 'status', 'created_at')
    search_fields = (
        'reporter__username',
        'kit__user__username',
        'kit__kit__team__name',
        'kit__kit__season',
        'kit__kit__kit_type',
        'description',
    )


class ConversationAdmin(admin.ModelAdmin):
    list_display = ('participant_one', 'participant_two', 'updated_at', 'created_at')
    list_filter = ('updated_at', 'created_at')
    search_fields = ('participant_one__username', 'participant_two__username')


class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'body_preview', 'created_at', 'read_at')
    list_filter = ('created_at', 'read_at')
    search_fields = (
        'sender__username',
        'conversation__participant_one__username',
        'conversation__participant_two__username',
        'body',
    )

    @admin.display(description='Message')
    def body_preview(self, obj):
        return obj.body[:60]


admin.site.register(Team, TeamAdmin)
admin.site.register(Kit, KitAdmin)
admin.site.register(UserKit, UserKitAdmin)
admin.site.register(KitType, KitTypeAdmin)
admin.site.register(KitTypeAlias, KitTypeAliasAdmin)
admin.site.register(TeamSeasonKitType, TeamSeasonKitTypeAdmin)
admin.site.register(ShirtVersion, ShirtVersionAdmin)
admin.site.register(KitReport, KitReportAdmin)
admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Country, CountryAdmin)
admin.site.register(League, LeagueAdmin)
