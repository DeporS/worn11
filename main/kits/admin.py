from django.contrib import admin
from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.db.models import Count
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Team, Kit, UserKit, UserKitImage, Profile, Country, League
from .forms import MergeTeamForm

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


@admin.action(description='Merge selected teams into one')
def merge_teams_action(modeladmin, request, queryset):
    # If this is a POST (form submission)
    if 'apply' in request.POST:
        dest_team_id = request.POST.get('destination_team')
        dest_team = Team.objects.get(id=dest_team_id)
        
        count = 0
        for team in queryset:
            if team == dest_team:
                continue
            
            # 1. Reassign all Kits from the incorrect team to the correct one
            # We use update() to do this in bulk
            Kit.objects.filter(team=team).update(team=dest_team)
            
            # 2. Delete the incorrect team
            team.delete()
            count += 1
            
        modeladmin.message_user(request, f"Successfully merged {count} teams into {dest_team.name}.")
        return HttpResponseRedirect(request.get_full_path())

    # If this is a GET (displaying the selection form)
    form = MergeTeamForm(teams=queryset) # Pass the queryset to limit choices
    return render(request, 'admin/merge_teams.html', context={'teams': queryset, 'form': form})

# Register in admin
class TeamAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'kits_in_collections_count', 'kits_definitions_count', 'is_verified']

    list_filter = ['is_verified']

    search_fields = ['name']

    actions = [merge_teams_action]

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
    list_display = ('name', 'flag')
    search_fields = ('name',)

# League Admin
class LeagueAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'hex_color', 'order', 'logo')
    list_filter = ('country',)
    search_fields = ('name', 'country__name')


admin.site.register(Team, TeamAdmin)
admin.site.register(Kit, KitAdmin)
admin.site.register(UserKit, UserKitAdmin)
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Country, CountryAdmin)
admin.site.register(League, LeagueAdmin)