from django.contrib import admin
from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect
from .models import Team, Kit, UserKit, UserKitImage

class UserKitImageInline(admin.TabularInline):
    model = UserKitImage
    extra = 1 # Number of extra forms to display

class UserKitAdmin(admin.ModelAdmin):
    list_display = ('user', 'kit', 'size', 'condition', 'shirt_technology', 'final_value', 'for_sale')
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
    list_display = ['name', 'is_verified']
    list_filter = ['is_verified']
    search_fields = ['name']
    actions = [merge_teams_action]

admin.site.register(Team, TeamAdmin)
admin.site.register(Kit)
admin.site.register(UserKit, UserKitAdmin)