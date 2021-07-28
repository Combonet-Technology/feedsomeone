from django.contrib import admin
from import_export.admin import ImportExportActionModelAdmin
from user.models import Profile


# Register your models here.
# admin.site.register(Profile)
@admin.register(Profile)
class ProfileAdmin(ImportExportActionModelAdmin):
    list_display = ('user', 'phone_number', 'state', 'date_joined', 'active')
    list_filter = ('active', 'date_joined')
    search_fields = ('state', 'phone_number')
    actions = ['approve_profile', 'disapprove_profile']

    def approve_profile(self, request, queryset):
        queryset.update(active=True)

    def disapprove_profile(self, request, queryset):
        queryset.update(active=False)


