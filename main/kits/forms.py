from django import forms
from .models import Team

class TeamWithStatusChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # How text will be displayed in the dropdown
        label = f"{obj.name}"
        
        # is_verified status
        if obj.is_verified:
            label += " ✅ (Verified)"
        else:
            label += " ❌ (Not Verified)"
            
        # ID for clarity
        label += f" [ID: {obj.id}]"
        
        return label

class MergeTeamForm(forms.Form):
    # Custom dropdown field to select destination team
    destination_team = TeamWithStatusChoiceField(
        queryset=Team.objects.none(), 
        label="Destination Team",
        empty_label=None # Force selection
    )

    def __init__(self, *args, **kwargs):
        # get the teams queryset passed from the admin action
        teams_queryset = kwargs.pop('teams', None)
        
        super(MergeTeamForm, self).__init__(*args, **kwargs)

        # If we passed teams, set them as the only possible options
        if teams_queryset is not None:
            self.fields['destination_team'].queryset = teams_queryset