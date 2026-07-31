from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from user.forms import UserProfileAdminChangeForm, UserProfileAdminCreationForm
from user.models import TeamMember, UserProfile, Volunteer


# Register your models here.
@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    add_form = UserProfileAdminCreationForm
    form = UserProfileAdminChangeForm
    model = UserProfile
    list_display = (
        'email',
        'first_name',
        'last_name',
        'is_active',
        'is_staff',
        'is_superuser',
        'date_joined',
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups', 'date_joined')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)
    readonly_fields = ('date_joined', 'date_updated')
    filter_horizontal = ('groups', 'user_permissions')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal information', {'fields': ('username', 'first_name', 'last_name')}),
        (
            'Access',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                ),
            },
        ),
        ('Record', {'fields': ('date_joined', 'date_updated')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'first_name',
                    'last_name',
                    'password1',
                    'password2',
                    'is_active',
                    'is_staff',
                    'groups',
                ),
            },
        ),
    )
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


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'role_title',
        'engagement_type',
        'status',
        'start_date',
        'access_granted_at',
    )
    list_filter = ('status', 'engagement_type', 'start_date')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'role_title')
    readonly_fields = (
        'user',
        'source_application',
        'activated_at',
        'access_granted_at',
        'access_granted_by',
        'access_revoked_at',
        'access_revoked_by',
        'invitation_sent_at',
        'invitation_message_id',
        'invitation_error',
        'created_at',
        'updated_at',
    )

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False
