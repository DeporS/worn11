from django.contrib import admin
from .models import Team, Kit, UserKit, UserKitImage

class UserKitImageInline(admin.TabularInline):
    model = UserKitImage
    extra = 1 # Number of extra forms to display

class UserKitAdmin(admin.ModelAdmin):
    list_display = ('user', 'kit', 'size', 'condition', 'shirt_technology', 'final_value', 'for_sale')
    inlines = [UserKitImageInline] # Include the inline images

admin.site.register(Team)
admin.site.register(Kit)
admin.site.register(UserKit, UserKitAdmin)