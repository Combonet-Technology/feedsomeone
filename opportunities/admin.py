from django.contrib import admin
from django.urls import reverse

from .models import Vacancy, VacancyApplication
from .notifications import notify_new_application


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'team',
        'engagement_type',
        'work_mode',
        'status',
        'positions_available',
        'display_order',
        'is_active',
        'published_at',
    )
    list_filter = ('status', 'engagement_type', 'work_mode', 'team', 'is_active')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'team', 'summary', 'description')
    readonly_fields = ('catalogue_version', 'created_at', 'updated_at')
    fieldsets = (
        (
            'Role',
            {
                'fields': (
                    'title',
                    'slug',
                    'team',
                    'summary',
                    'engagement_type',
                    'work_mode',
                    'location',
                    'time_commitment',
                    'positions_available',
                    'display_order',
                ),
            },
        ),
        (
            'Vacancy content',
            {
                'fields': (
                    'about_oef',
                    'description',
                    'who_we_are_looking_for',
                    'responsibilities',
                    'expectations',
                    'benefits',
                ),
            },
        ),
        (
            'Publishing',
            {
                'fields': (
                    'status',
                    'is_active',
                    'published_at',
                    'catalogue_version',
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )


@admin.register(VacancyApplication)
class VacancyApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'vacancy',
        'full_name',
        'email',
        'status',
        'newsletter_opt_in',
        'newsletter_subscribed_at',
        'acknowledgement_sent_at',
        'slack_notified_at',
        'created_at',
    )
    list_filter = ('status', 'vacancy')
    search_fields = ('vacancy__title', 'full_name', 'email')
    readonly_fields = (
        'acknowledgement_sent_at',
        'slack_notified_at',
        'newsletter_subscribed_at',
        'notification_error',
        'created_at',
        'updated_at',
    )
    actions = ('retry_notifications',)

    @admin.action(description='Send or retry missing notifications')
    def retry_notifications(self, request, queryset):
        successful = 0
        incomplete = 0
        for application in queryset.select_related('vacancy'):
            sent = notify_new_application(
                application,
                site_url=request.build_absolute_uri('/'),
                admin_url=request.build_absolute_uri(
                    reverse(
                        'admin:opportunities_vacancyapplication_change',
                        args=(application.pk,),
                    )
                ),
            )
            if sent:
                successful += 1
            else:
                incomplete += 1

        self.message_user(
            request,
            (
                f'Notifications complete for {successful} application(s). '
                f'{incomplete} still have a delivery error.'
            ),
        )
