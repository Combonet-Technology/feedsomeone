from django.contrib import admin
from import_export.admin import ImportExportActionModelAdmin
from user.models import UserProfile


# Register your models here.
@admin.register(UserProfile)
class ProfileAdmin(ImportExportActionModelAdmin):
    list_display = ('first_name', 'last_name', 'phone_number',
                    'state', 'date_joined', 'is_active')
    list_filter = ('is_active', 'date_joined')
    search_fields = ('state', 'phone_number')
    actions = ['approve_profile', 'disapprove_profile']

    def verify_profile(self, request, queryset):
        queryset.update(is_verified=True)

    def suspend_profile(self, request, queryset):
        queryset.update(is_verified=False)

    def enable_user(self, request, queryset):
        queryset.update(is_active=True)

    def disable_user(self, request, queryset):
        queryset.update(is_active=False)
