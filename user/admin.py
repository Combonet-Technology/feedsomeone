from django.contrib import admin
from import_export.admin import ImportExportActionModelAdmin

from user.models import UserProfile, Volunteer


# Register your models here.
@admin.register(UserProfile)
class UserProfileAdmin(ImportExportActionModelAdmin):
    list_display = ('first_name', 'last_name',
                    'date_joined', 'is_active',)
    list_filter = ('is_active', 'date_joined')
    search_fields = ('state',)
    actions = ['verify_profile', 'suspend_profile',
               'enable_user', 'disable_user']

    def verify_profile(self, request, queryset):
        queryset.update(is_active=True)

    def suspend_profile(self, request, queryset):
        queryset.update(is_active=False)

    def enable_user(self, request, queryset):
        queryset.update(is_active=True)

    def disable_user(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    list_display = ('user', 'profession', 'is_verified', 'ethnicity', 'religion')
    list_filter = ('is_verified',)
    search_fields = ('state_of_residence', 'ethnicity', 'phone_number')
