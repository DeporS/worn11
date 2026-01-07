from django.contrib import admin
from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.db.models import Count
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Team, Kit, UserKit, UserKitImage, Profile

class UserKitImageInline(admin.TabularInline):
    model = UserKitImage
    extra = 1 # Number of extra forms to display

class UserKitAdmin(admin.ModelAdmin):
    list_display = ('user', 'kit', 'size', 'condition', 'shirt_technology', 'final_value', 'for_sale', 'added_at')
    list_filter = ('size', 'condition', 'shirt_technology', 'for_sale', 'added_at')
    search_fields = ('user__username', 'kit__team__name', 'kit__season', 'kit__kit_type')

    readonly_fields = ('final_value', 'added_at')

    inlines = [UserKitImageInline] # Include the inline images

class MergeTeamForm(forms.Form):
    # Form for selecting the destination team
    destination_team = forms.ModelChoiceField(queryset=Team.objects.all())

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
    form = MergeTeamForm()
    return render(request, 'admin/merge_teams.html', context={'teams': queryset, 'form': form})

# Register in admin
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_verified', 'kits_count']
    list_filter = ['is_verified']
    search_fields = ['name']
    actions = [merge_teams_action]

    # Count of kits related to the team
    def kits_count(self, obj):
        return obj.kits.count()
    
    kits_count.short_description = 'Kits in DB' # Column name
    kits_count.admin_order_field = 'kits_count' # Allow sorting by this field
    
    # Optimize database query
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(kits_count=Count('kits'))

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


admin.site.register(Team, TeamAdmin)
admin.site.register(Kit)
admin.site.register(UserKit, UserKitAdmin)
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
