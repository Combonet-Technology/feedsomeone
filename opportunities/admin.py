import logging

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .forms import VolunteerOfferForm
from .models import Vacancy, VacancyApplication, VolunteerOffer
from .notifications import notify_new_application
from .offers import (OfferAlreadySent, OfferDeliveryInProgress,
                     send_volunteer_offer)

logger = logging.getLogger(__name__)


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
    change_form_template = 'admin/opportunities/vacancyapplication/change_form.html'
    list_display = (
        'vacancy',
        'full_name',
        'email',
        'status',
        'offer_delivery_status',
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
        'offer_delivery_status',
        'offer_sent_at',
        'offer_sent_by',
        'offer_letter',
        'offer_delivery_error',
        'created_at',
        'updated_at',
    )
    fieldsets = (
        (
            'Application',
            {
                'fields': (
                    'vacancy',
                    'applicant',
                    'full_name',
                    'email',
                    'phone',
                    'cv',
                    'cover_letter',
                    'status',
                ),
            },
        ),
        (
            'Volunteer offer',
            {
                'fields': (
                    'offer_delivery_status',
                    'offer_sent_at',
                    'offer_sent_by',
                    'offer_letter',
                    'offer_delivery_error',
                ),
            },
        ),
        (
            'Application notifications',
            {
                'classes': ('collapse',),
                'fields': (
                    'newsletter_opt_in',
                    'newsletter_subscribed_at',
                    'acknowledgement_sent_at',
                    'slack_notified_at',
                    'notification_error',
                ),
            },
        ),
        ('Record', {'classes': ('collapse',), 'fields': ('created_at', 'updated_at')}),
    )
    actions = ('retry_notifications',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('vacancy', 'volunteer_offer')

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/send-volunteer-offer/',
                self.admin_site.admin_view(self.send_volunteer_offer_view),
                name='opportunities_vacancyapplication_send_offer',
            ),
        ]
        return custom_urls + super().get_urls()

    def has_send_offer_permission(self, request, obj=None):
        return request.user.has_perm('opportunities.send_volunteer_offer')

    @staticmethod
    def _offer_for(obj):
        try:
            return obj.volunteer_offer
        except VolunteerOffer.DoesNotExist:
            return None

    @admin.display(description='Offer')
    def offer_delivery_status(self, obj):
        offer = self._offer_for(obj)
        return offer.get_delivery_status_display() if offer else 'Not prepared'

    @admin.display(description='Offer sent at')
    def offer_sent_at(self, obj):
        offer = self._offer_for(obj)
        return offer.sent_at if offer else None

    @admin.display(description='Offer sent by')
    def offer_sent_by(self, obj):
        offer = self._offer_for(obj)
        return offer.sent_by if offer else None

    @admin.display(description='Offer letter')
    def offer_letter(self, obj):
        offer = self._offer_for(obj)
        if not offer or not offer.letter_pdf:
            return 'Not generated'
        return format_html('<a href="{}">Download PDF</a>', offer.letter_pdf.url)

    @admin.display(description='Offer delivery error')
    def offer_delivery_error(self, obj):
        offer = self._offer_for(obj)
        return offer.delivery_error if offer else ''

    def render_change_form(self, request, context, *args, **kwargs):
        application = context.get('original')
        offer = self._offer_for(application) if application else None
        context['show_send_volunteer_offer'] = bool(
            application
            and self.has_send_offer_permission(request, application)
            and not (offer and offer.sent_at)
        )
        if application:
            context['send_volunteer_offer_url'] = reverse(
                'admin:opportunities_vacancyapplication_send_offer',
                args=(application.pk,),
            )
        return super().render_change_form(request, context, *args, **kwargs)

    @staticmethod
    def _default_work_arrangement(vacancy):
        if vacancy.work_mode == 'onsite':
            return f'On-site in {vacancy.location}, according to agreed working arrangements'
        if vacancy.work_mode == 'hybrid':
            return (
                f'Hybrid in {vacancy.location}, with remote hours and in-person activity '
                'agreed in advance'
            )
        return 'Remote, with hours arranged flexibly around agreed priorities and deadlines'

    def _offer_initial(self, application):
        offer = self._offer_for(application)
        if offer:
            return {
                'start_date': offer.start_date,
                'initial_period': offer.initial_period,
                'weekly_commitment': offer.weekly_commitment,
                'work_arrangement': offer.work_arrangement,
                'reporting_contact': offer.reporting_contact,
                'role_contribution': offer.role_contribution,
                'acceptance_deadline': offer.acceptance_deadline,
            }
        return {
            'start_date': timezone.localdate(),
            'initial_period': 'Three months',
            'weekly_commitment': application.vacancy.time_commitment or '10 hours per week',
            'work_arrangement': self._default_work_arrangement(application.vacancy),
            'reporting_contact': settings.OEF_VOLUNTEER_REPORTING_CONTACT,
            'role_contribution': application.vacancy.summary,
        }

    def send_volunteer_offer_view(self, request, object_id):
        application = self.get_object(request, object_id)
        if application is None:
            return HttpResponseRedirect(reverse('admin:opportunities_vacancyapplication_changelist'))
        if not self.has_send_offer_permission(request, application):
            raise PermissionDenied

        existing_offer = self._offer_for(application)
        if existing_offer and existing_offer.sent_at:
            self.message_user(
                request,
                'An offer has already been sent to this applicant.',
                level=messages.WARNING,
            )
            return HttpResponseRedirect(
                reverse(
                    'admin:opportunities_vacancyapplication_change',
                    args=(application.pk,),
                )
            )

        form = VolunteerOfferForm(
            request.POST or None,
            initial=self._offer_initial(application),
        )
        if request.method == 'POST' and form.is_valid():
            try:
                offer = send_volunteer_offer(application, form.cleaned_data, request.user)
            except (OfferAlreadySent, OfferDeliveryInProgress) as error:
                form.add_error(None, str(error))
            except Exception:
                logger.exception(
                    'Volunteer offer delivery failed for application %s',
                    application.pk,
                )
                form.add_error(
                    None,
                    'The offer could not be sent. No application status was changed. '
                    'Review the recorded delivery error and try again.',
                )
            else:
                self.message_user(
                    request,
                    f'Volunteer offer sent to {offer.recipient_email}.',
                    level=messages.SUCCESS,
                )
                return HttpResponseRedirect(
                    reverse(
                        'admin:opportunities_vacancyapplication_change',
                        args=(application.pk,),
                    )
                )

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Prepare and send volunteer offer',
            'application': application,
            'form': form,
            'media': self.media + form.media,
            'change_url': reverse(
                'admin:opportunities_vacancyapplication_change',
                args=(application.pk,),
            ),
        }
        return TemplateResponse(
            request,
            'admin/opportunities/vacancyapplication/send_offer.html',
            context,
        )

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
