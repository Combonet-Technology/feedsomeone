import logging

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from user.models import TeamMember

from .forms import (StaffAccessGrantForm, StaffAccessRevocationForm,
                    VolunteerOfferForm, VolunteerOnboardingEmailForm)
from .models import (Vacancy, VacancyApplication, VolunteerOffer,
                     VolunteerOnboarding)
from .notifications import notify_new_application
from .offers import OfferDeliveryInProgress, send_volunteer_offer
from .onboarding import \
    ELIGIBLE_APPLICATION_STATUSES as ELIGIBLE_ONBOARDING_STATUSES
from .onboarding import OnboardingEmailError, send_onboarding_email
from .rejections import send_rejection_email_batch
from .staff_access import (ELIGIBLE_APPLICATION_STATUSES, StaffAccessError,
                           grant_staff_access, revoke_staff_access)

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
        'onboarding_delivery_status',
        'rejection_email_delivery_status',
        'team_access_status',
        'newsletter_opt_in',
        'newsletter_subscribed_at',
        'acknowledgement_sent_at',
        'slack_notified_at',
        'created_at',
    )
    list_filter = ('status', 'vacancy', 'newsletter_opt_in')
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
        'onboarding_delivery_status',
        'onboarding_email_summary',
        'rejection_email_delivery_status',
        'rejection_email_summary',
        'team_access_status',
        'team_access_account',
        'team_access_invited_at',
        'team_access_error',
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
            'Volunteer onboarding',
            {
                'fields': (
                    'onboarding_delivery_status',
                    'onboarding_email_summary',
                ),
            },
        ),
        (
            'Application outcome email',
            {
                'fields': (
                    'rejection_email_delivery_status',
                    'rejection_email_summary',
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
        (
            'Team access',
            {
                'classes': ('collapse',),
                'fields': (
                    'team_access_status',
                    'team_access_account',
                    'team_access_invited_at',
                    'team_access_error',
                ),
            },
        ),
        ('Record', {'classes': ('collapse',), 'fields': ('created_at', 'updated_at')}),
    )
    actions = ('send_rejection_emails', 'retry_notifications')

    applicant_submitted_fields = (
        'vacancy',
        'applicant',
        'full_name',
        'email',
        'phone',
        'cv',
        'cover_letter',
        'newsletter_opt_in',
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly_fields.extend(self.applicant_submitted_fields)
        return tuple(dict.fromkeys(readonly_fields))

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'vacancy',
            'volunteer_offer',
            'volunteer_onboarding',
            'team_member__user',
        )

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/send-volunteer-offer/',
                self.admin_site.admin_view(self.send_volunteer_offer_view),
                name='opportunities_vacancyapplication_send_offer',
            ),
            path(
                '<path:object_id>/send-onboarding-email/',
                self.admin_site.admin_view(self.send_onboarding_email_view),
                name='opportunities_vacancyapplication_send_onboarding',
            ),
            path(
                '<path:object_id>/staff-access/',
                self.admin_site.admin_view(self.staff_access_view),
                name='opportunities_vacancyapplication_staff_access',
            ),
        ]
        return custom_urls + super().get_urls()

    def has_send_offer_permission(self, request, obj=None):
        return request.user.has_perm('opportunities.send_volunteer_offer')

    def has_send_onboarding_permission(self, request, obj=None):
        return request.user.has_perm('opportunities.send_onboarding_email')

    def has_send_rejection_permission(self, request):
        return request.user.has_perm('opportunities.send_rejection_email')

    @staticmethod
    def has_manage_staff_access_permission(request):
        return request.user.is_active and request.user.is_superuser

    @staticmethod
    def _offer_for(obj):
        try:
            return obj.volunteer_offer
        except VolunteerOffer.DoesNotExist:
            return None

    @staticmethod
    def _team_member_for(obj):
        try:
            return obj.team_member
        except TeamMember.DoesNotExist:
            return None

    @staticmethod
    def _onboarding_for(obj):
        try:
            return obj.volunteer_onboarding
        except VolunteerOnboarding.DoesNotExist:
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

    @admin.display(description='Onboarding email')
    def onboarding_delivery_status(self, obj):
        onboarding = self._onboarding_for(obj)
        return onboarding.get_delivery_status_display() if onboarding else 'Not sent'

    @admin.display(description='Onboarding email history')
    def onboarding_email_summary(self, obj):
        onboarding = self._onboarding_for(obj)
        if not onboarding:
            return 'Not sent'
        return format_html(
            'Successful sends: {}<br>First sent: {}<br>Last sent: {}<br>'
            'Last sent by: {}<br>Delivery error: {}',
            onboarding.send_count,
            onboarding.first_sent_at or '—',
            onboarding.last_sent_at or '—',
            onboarding.last_sent_by or '—',
            onboarding.delivery_error or '—',
        )

    @admin.display(description='Outcome email')
    def rejection_email_delivery_status(self, obj):
        return obj.get_rejection_email_status_display()

    @admin.display(description='Outcome email history')
    def rejection_email_summary(self, obj):
        return format_html(
            'Sent at: {}<br>Sent by: {}<br>Brevo message ID: {}<br>'
            'Delivery error: {}',
            obj.rejection_email_sent_at or '—',
            obj.rejection_email_sent_by or '—',
            obj.rejection_email_message_id or '—',
            obj.rejection_email_error or '—',
        )

    @admin.display(description='Staff access')
    def team_access_status(self, obj):
        team_member = self._team_member_for(obj)
        return team_member.get_status_display() if team_member else 'Not granted'

    @admin.display(description='Staff account')
    def team_access_account(self, obj):
        team_member = self._team_member_for(obj)
        return team_member.user.email if team_member else ''

    @admin.display(description='Invitation sent at')
    def team_access_invited_at(self, obj):
        team_member = self._team_member_for(obj)
        return team_member.invitation_sent_at if team_member else None

    @admin.display(description='Invitation error')
    def team_access_error(self, obj):
        team_member = self._team_member_for(obj)
        return team_member.invitation_error if team_member else ''

    def render_change_form(self, request, context, *args, **kwargs):
        application = context.get('original')
        offer = self._offer_for(application) if application else None
        team_member = self._team_member_for(application) if application else None
        onboarding = self._onboarding_for(application) if application else None
        staff_access_is_current = bool(
            team_member and team_member.status in {'invited', 'onboarding', 'active'}
        )
        can_send_offer = bool(
            application and self.has_send_offer_permission(request, application)
        )
        can_manage_staff_access = bool(
            application
            and self.has_manage_staff_access_permission(request)
            and (application.status in ELIGIBLE_APPLICATION_STATUSES or team_member)
        )
        has_onboarding_permission = bool(
            application
            and self.has_send_onboarding_permission(request, application)
        )
        can_send_onboarding = bool(
            has_onboarding_permission
            and application.status in ELIGIBLE_ONBOARDING_STATUSES
        )
        context['show_recruitment_actions'] = bool(application)
        context['can_send_volunteer_offer'] = can_send_offer
        context['send_volunteer_offer_label'] = (
            'Resend offer' if offer and offer.sent_at else 'Send offer'
        )
        context['send_volunteer_offer_disabled_reason'] = (
            '' if can_send_offer else 'You do not have permission to send volunteer offers.'
        )
        context['can_send_onboarding'] = can_send_onboarding
        context['send_onboarding_label'] = (
            'Resend onboarding email'
            if onboarding and onboarding.send_count
            else 'Start onboarding'
        )
        if not has_onboarding_permission:
            context['send_onboarding_disabled_reason'] = (
                'You do not have permission to start volunteer onboarding.'
            )
        elif application.status not in ELIGIBLE_ONBOARDING_STATUSES:
            context['send_onboarding_disabled_reason'] = (
                'Set the application status to Onboarding before starting onboarding.'
            )
        else:
            context['send_onboarding_disabled_reason'] = ''
        context['can_manage_staff_access'] = can_manage_staff_access
        context['staff_access_is_current'] = staff_access_is_current
        if staff_access_is_current:
            context['staff_access_label'] = 'Resend access email'
        elif team_member:
            context['staff_access_label'] = 'Restore staff access'
        else:
            context['staff_access_label'] = 'Grant staff access'
        context['show_revoke_staff_access'] = staff_access_is_current
        context['can_revoke_staff_access'] = bool(
            staff_access_is_current
            and self.has_manage_staff_access_permission(request)
        )
        if not self.has_manage_staff_access_permission(request):
            context['staff_access_disabled_reason'] = (
                'Only the OEF superuser can grant or revoke staff access.'
            )
        elif (
            application
            and not team_member
            and application.status not in ELIGIBLE_APPLICATION_STATUSES
        ):
            context['staff_access_disabled_reason'] = (
                'The volunteer agreement must be signed before staff access is granted.'
            )
        else:
            context['staff_access_disabled_reason'] = ''
        context['revoke_staff_access_disabled_reason'] = (
            ''
            if context['can_revoke_staff_access']
            else 'Only the OEF superuser can revoke staff access.'
        )
        if application:
            context['send_volunteer_offer_url'] = reverse(
                'admin:opportunities_vacancyapplication_send_offer',
                args=(application.pk,),
            )
            context['staff_access_url'] = reverse(
                'admin:opportunities_vacancyapplication_staff_access',
                args=(application.pk,),
            )
            context['send_onboarding_url'] = reverse(
                'admin:opportunities_vacancyapplication_send_onboarding',
                args=(application.pk,),
            )
            context['resend_staff_access_url'] = f"{context['staff_access_url']}#resend-access"
            context['revoke_staff_access_url'] = f"{context['staff_access_url']}#revoke-access"
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
        is_resend = bool(existing_offer and existing_offer.sent_at)

        form = VolunteerOfferForm(
            request.POST or None,
            initial=self._offer_initial(application),
        )
        if is_resend:
            form.fields['confirm_send'].label = (
                'I have reviewed the recipient and engagement terms and confirm that '
                'this offer should be resent.'
            )
        if request.method == 'POST' and form.is_valid():
            try:
                offer = send_volunteer_offer(application, form.cleaned_data, request.user)
            except OfferDeliveryInProgress as error:
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
                    (
                        f'Volunteer offer resent to {offer.recipient_email}.'
                        if is_resend
                        else f'Volunteer offer sent to {offer.recipient_email}.'
                    ),
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
            'title': (
                'Resend volunteer offer'
                if is_resend
                else 'Send volunteer offer'
            ),
            'application': application,
            'existing_offer': existing_offer,
            'is_resend': is_resend,
            'submit_label': 'Resend offer' if is_resend else 'Send offer',
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

    def send_onboarding_email_view(self, request, object_id):
        application = self.get_object(request, object_id)
        if application is None:
            return HttpResponseRedirect(
                reverse('admin:opportunities_vacancyapplication_changelist')
            )
        if not self.has_send_onboarding_permission(request, application):
            raise PermissionDenied

        onboarding = self._onboarding_for(application)
        send_count = onboarding.send_count if onboarding else 0
        is_resend = bool(send_count)
        form = VolunteerOnboardingEmailForm(
            request.POST or None,
            initial={'expected_send_count': send_count},
        )
        if is_resend:
            form.fields['confirm_send'].label = (
                'I understand that this volunteer has already received the onboarding '
                'email and confirm that another copy should be sent.'
            )

        if request.method == 'POST' and form.is_valid():
            try:
                onboarding = send_onboarding_email(
                    application,
                    request.user,
                    form.cleaned_data['expected_send_count'],
                )
            except OnboardingEmailError as error:
                form.add_error(None, str(error))
            except Exception:
                logger.exception(
                    'Volunteer onboarding email failed for application %s',
                    application.pk,
                )
                form.add_error(
                    None,
                    'The onboarding email could not be sent. Review the recorded '
                    'delivery error and try again.',
                )
            else:
                self.message_user(
                    request,
                    (
                        f'Onboarding email resent to {application.email}.'
                        if is_resend
                        else f'Onboarding started for {application.email}.'
                    ),
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
            'title': (
                'Resend onboarding email' if is_resend else 'Start onboarding'
            ),
            'application': application,
            'onboarding': onboarding,
            'is_resend': is_resend,
            'submit_label': (
                'Resend onboarding email' if is_resend else 'Start onboarding'
            ),
            'form': form,
            'media': self.media + form.media,
            'change_url': reverse(
                'admin:opportunities_vacancyapplication_change',
                args=(application.pk,),
            ),
        }
        return TemplateResponse(
            request,
            'admin/opportunities/vacancyapplication/send_onboarding.html',
            context,
        )

    def _staff_access_initial(self, application, team_member):
        return {
            'role_title': (
                team_member.role_title if team_member else application.vacancy.title
            ),
            'engagement_type': (
                team_member.engagement_type
                if team_member
                else application.vacancy.engagement_type
            ),
            'start_date': team_member.start_date if team_member else None,
        }

    def staff_access_view(self, request, object_id):
        application = self.get_object(request, object_id)
        if application is None:
            return HttpResponseRedirect(
                reverse('admin:opportunities_vacancyapplication_changelist')
            )
        if not self.has_manage_staff_access_permission(request):
            raise PermissionDenied

        team_member = self._team_member_for(application)
        action = request.POST.get('action', 'grant')
        grant_form = StaffAccessGrantForm(
            request.POST if request.method == 'POST' and action == 'grant' else None,
            initial=self._staff_access_initial(application, team_member),
        )
        revoke_form = StaffAccessRevocationForm(
            request.POST if request.method == 'POST' and action == 'revoke' else None,
        )

        if request.method == 'POST' and action == 'grant' and grant_form.is_valid():
            try:
                result = grant_staff_access(
                    application,
                    grant_form.cleaned_data,
                    request.user,
                    request.build_absolute_uri('/'),
                )
            except StaffAccessError as error:
                grant_form.add_error(None, str(error))
            except Exception:
                logger.exception(
                    'Staff access invitation failed for application %s',
                    application.pk,
                )
                grant_form.add_error(
                    None,
                    'The account was prepared, but the invitation could not be sent. '
                    'Review the recorded error and retry when email delivery is available.',
                )
            else:
                message = 'Staff access granted and invitation sent.'
                if not result.password_setup_required:
                    message = 'Staff access granted and login notification sent.'
                self.message_user(request, message, level=messages.SUCCESS)
                return HttpResponseRedirect(
                    reverse(
                        'admin:opportunities_vacancyapplication_change',
                        args=(application.pk,),
                    )
                )

        if request.method == 'POST' and action == 'revoke' and revoke_form.is_valid():
            try:
                revoke_staff_access(application, request.user)
            except StaffAccessError as error:
                revoke_form.add_error(None, str(error))
            else:
                self.message_user(
                    request,
                    'Recruitment Manager access revoked. The user and team record were retained.',
                    level=messages.SUCCESS,
                )
                return HttpResponseRedirect(
                    reverse(
                        'admin:opportunities_vacancyapplication_change',
                        args=(application.pk,),
                    )
                )

        team_member = self._team_member_for(
            self.get_queryset(request).get(pk=application.pk)
        )
        access_is_current = bool(
            team_member and team_member.status in {'invited', 'onboarding', 'active'}
        )
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Manage staff access',
            'application': application,
            'team_member': team_member,
            'access_is_current': access_is_current,
            'grant_form': grant_form,
            'revoke_form': revoke_form,
            'staff_access_submit_label': (
                'Resend access email'
                if access_is_current
                else (
                    'Restore access and send email'
                    if team_member
                    else 'Grant access and send invitation'
                )
            ),
            'change_url': reverse(
                'admin:opportunities_vacancyapplication_change',
                args=(application.pk,),
            ),
        }
        return TemplateResponse(
            request,
            'admin/opportunities/vacancyapplication/staff_access.html',
            context,
        )

    @admin.action(
        permissions=('send_rejection',),
        description='Send rejection emails to selected applicants',
    )
    def send_rejection_emails(self, request, queryset):
        selected_count = queryset.count()
        eligible_count = queryset.filter(
            status='not_selected',
        ).exclude(
            rejection_email_status='sent',
        ).count()
        already_sent_count = queryset.filter(
            rejection_email_status='sent',
        ).count()
        wrong_status_count = queryset.exclude(status='not_selected').count()

        if 'confirm_rejection_send' not in request.POST:
            context = {
                **self.admin_site.each_context(request),
                'opts': self.model._meta,
                'title': 'Confirm rejection email send',
                'queryset': queryset,
                'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
                'selected_count': selected_count,
                'eligible_count': eligible_count,
                'already_sent_count': already_sent_count,
                'wrong_status_count': wrong_status_count,
            }
            return TemplateResponse(
                request,
                'admin/opportunities/vacancyapplication/send_rejections.html',
                context,
            )

        result = send_rejection_email_batch(queryset, request.user)
        level = messages.ERROR if result.failed else messages.SUCCESS
        self.message_user(
            request,
            (
                f'Rejection email batch complete: {result.sent} sent, '
                f'{result.failed} failed, {result.skipped_already_sent} already sent, '
                f'{result.skipped_wrong_status} not eligible, and '
                f'{result.skipped_in_progress} already processing.'
            ),
            level=level,
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
