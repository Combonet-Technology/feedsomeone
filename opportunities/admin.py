import logging

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from opportunities.interviews import send_interview_invitation_batch
from user.models import TeamMember, UserProfile
from user.workforce import appoint_candidate

from .forms import VolunteerOfferForm, VolunteerOnboardingEmailForm
from .models import (RecruitmentCohort, Vacancy, VacancyApplication,
                     VolunteerOffer, VolunteerOnboarding)
from .notifications import notify_new_application
from .offers import OfferDeliveryInProgress, send_volunteer_offer
from .onboarding import \
    ELIGIBLE_APPLICATION_STATUSES as ELIGIBLE_ONBOARDING_STATUSES
from .onboarding import OnboardingEmailError, send_onboarding_email
from .recruitment import has_duplicate_application
from .rejections import send_rejection_email_batch

logger = logging.getLogger(__name__)


@admin.register(RecruitmentCohort)
class RecruitmentCohortAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'status', 'opened_at', 'intake_closed_at', 'completed_at')
    list_filter = ('status',)
    search_fields = ('code', 'name')
    readonly_fields = ('opened_at', 'intake_closed_at', 'completed_at')

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj:
            fields.append('code')
        return fields


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'cohort':
            kwargs['empty_label'] = 'Unbatched'
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    list_display = (
        'title',
        'cohort',
        'team',
        'engagement_type',
        'work_mode',
        'status',
        'positions_available',
        'display_order',
        'is_active',
        'published_at',
    )
    list_filter = ('cohort', 'status', 'engagement_type', 'work_mode', 'team', 'is_active')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'team', 'summary', 'description')
    readonly_fields = ('catalogue_version', 'created_at', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.applications.exists():
            fields.extend(('slug', 'title', 'team', 'engagement_type'))
        return fields

    def get_prepopulated_fields(self, request, obj=None):
        if obj and obj.applications.exists():
            return {}
        return super().get_prepopulated_fields(request, obj)

    fieldsets = (
        (
            'Role',
            {
                'fields': (
                    'title',
                    'cohort',
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


class ApplicationQueueFilter(admin.SimpleListFilter):
    title = 'recruitment queue'
    parameter_name = 'queue'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Active recruitment'),
            ('appointed', 'Appointed'),
            ('completed', 'Other completed'),
            ('all', 'All applications'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'all' or (value is None and 'status__exact' in request.GET):
            return queryset
        if value == 'appointed':
            return queryset.filter(status=VacancyApplication.Status.APPOINTED)
        if value == 'completed':
            return queryset.filter(status__in=(
                'not_selected', 'withdrawn', 'closed',
                'offer_declined', 'agreement_declined', 'onboarding_failed',
            ))
        return queryset.filter(status__in=(
            'received', 'reviewing', 'shortlisted', 'offered',
            'offer_accepted', 'agreement_pending', 'agreement_signed',
            'onboarding', 'active',
        ))


class VacancyApplicationAdminForm(forms.ModelForm):
    class Meta:
        model = VacancyApplication
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        # Managers edit cohort while identity fields are readonly and excluded
        # from ModelForm constraint validation. Validate against that identity too.
        if 'cohort' in cleaned:
            vacancy = cleaned.get('vacancy', self.instance.vacancy if self.instance.vacancy_id else None)
            applicant = cleaned.get('applicant', self.instance.applicant)
            cohort = cleaned['cohort']
            if vacancy and has_duplicate_application(
                vacancy_id=vacancy.pk, cohort_id=cohort.pk if cohort else None,
                email=cleaned.get('email', self.instance.email),
                applicant_id=applicant.pk if applicant else None, exclude_pk=self.instance.pk,
            ):
                self.add_error('cohort', 'This person already has an application for this role in that cohort.')
        if cleaned.get('status') != VacancyApplication.Status.APPOINTED:
            return cleaned
        email = (cleaned['email'] if 'email' in cleaned else self.instance.email or '').strip().lower()
        applicant = cleaned['applicant'] if 'applicant' in cleaned else self.instance.applicant
        member = None
        if self.instance.pk:
            member = TeamMember.objects.select_related('user').filter(
                source_application_id=self.instance.pk,
            ).first()
        if member is None and applicant:
            member = TeamMember.objects.select_related('user').filter(user=applicant).first()
        if member is None and TeamMember.objects.filter(primary_email__iexact=email).exists():
            raise forms.ValidationError('A team member with this email exists. Reconcile the identity first.')
        if member and member.primary_email and member.primary_email.strip().lower() != email:
            raise forms.ValidationError('The linked team member email conflicts with this application.')
        account = member.user if member and member.user_id else applicant
        if account and account.email.strip().lower() != email:
            raise forms.ValidationError('The linked account email conflicts with this application.')
        if member and member.user_id and applicant and member.user_id != applicant.pk:
            raise forms.ValidationError('The linked team member has a different applicant account.')
        if account is None and UserProfile.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email exists. Reconcile the identity first.')
        if len(email) > UserProfile._meta.get_field('email').max_length:
            raise forms.ValidationError('This email is too long for a team account.')
        return cleaned


@admin.register(VacancyApplication)
class VacancyApplicationAdmin(admin.ModelAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'cohort':
            kwargs['empty_label'] = 'Unbatched'
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    form = VacancyApplicationAdminForm
    change_form_template = 'admin/opportunities/vacancyapplication/change_form.html'
    list_display = (
        'vacancy',
        'cohort',
        'full_name',
        'email',
        'status',
        'offer_delivery_status',
        'onboarding_delivery_status',
        'rejection_email_delivery_status',
        'newsletter_opt_in',
        'newsletter_subscribed_at',
        'acknowledgement_sent_at',
        'slack_notified_at',
        'created_at',
    )
    list_filter = (
        ApplicationQueueFilter,
        'status',
        'rejection_email_status',
        'vacancy',
        'cohort',
        'newsletter_opt_in',
    )
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
        'agreement_verified_at',
        'agreement_verified_by',
        'onboarding_completed_at',
        'onboarding_completed_by',
        'appointed_at',
        'appointed_by',
        'created_at',
        'updated_at',
    )
    fieldsets = (
        (
            'Application',
            {
                'fields': (
                    'vacancy',
                    'cohort',
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
        ('Transition audit', {'classes': ('collapse',), 'fields': (
            'agreement_verified_at', 'agreement_verified_by',
            'onboarding_completed_at', 'onboarding_completed_by',
            'appointed_at', 'appointed_by',
        )}),
        ('Record', {'classes': ('collapse',), 'fields': ('created_at', 'updated_at')}),
    )
    actions = ('send_acceptance_emails', 'shortlist_candidates', 'send_rejection_emails', 'retry_notifications')

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
        )

    def save_model(self, request, obj, form, change):
        if obj.status == VacancyApplication.Status.APPOINTED and (
            not change or 'status' in form.changed_data
        ):
            obj.status = (
                VacancyApplication.objects.values_list('status', flat=True).get(pk=obj.pk)
                if change else VacancyApplication.Status.RECEIVED
            )
            super().save_model(request, obj, form, change)
            appoint_candidate(obj, request.user)
            obj.refresh_from_db()
            return
        if change and 'status' in form.changed_data:
            if obj.status == VacancyApplication.Status.AGREEMENT_SIGNED:
                obj.agreement_verified_at = timezone.now()
                obj.agreement_verified_by = request.user
        super().save_model(request, obj, form, change)

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
        ]
        return custom_urls + super().get_urls()

    def has_send_offer_permission(self, request, obj=None):
        return request.user.has_perm('opportunities.send_volunteer_offer')

    def has_send_onboarding_permission(self, request, obj=None):
        return request.user.has_perm('opportunities.send_onboarding_email')

    def has_send_rejection_permission(self, request):
        return request.user.has_perm('opportunities.send_rejection_email')

    @staticmethod
    def _offer_for(obj):
        try:
            return obj.volunteer_offer
        except VolunteerOffer.DoesNotExist:
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

    def render_change_form(self, request, context, *args, **kwargs):
        application = context.get('original')
        offer = self._offer_for(application) if application else None
        onboarding = self._onboarding_for(application) if application else None
        can_send_offer = bool(
            application and self.has_send_offer_permission(request, application)
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
        if application:
            context['send_volunteer_offer_url'] = reverse(
                'admin:opportunities_vacancyapplication_send_offer',
                args=(application.pk,),
            )
            context['send_onboarding_url'] = reverse(
                'admin:opportunities_vacancyapplication_send_onboarding',
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
                'action_to': 'rejection',
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
                'admin/opportunities/vacancyapplication/interview_actions.html',
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

    @admin.action(
        description='shortlist Candidates for interview'
    )
    def shortlist_candidates(self, request, queryset):
        eligible_statuses = frozenset({
            VacancyApplication.Status.RECEIVED,
            VacancyApplication.Status.REVIEWING,
        })

        updated_count = queryset.filter(
            status__in=eligible_statuses,
        ).update(
            status=VacancyApplication.Status.SHORTLISTED,
            shortlisted_by=request.user,
            shortlisted_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated_count} application(s) shortlisted.",
            level=messages.SUCCESS,
        )

        # action worked but we should add tests for edge cases and also
        # checks for edge cases like already shorlisted candidates

    @admin.action(description='send interview emails')
    def send_acceptance_emails(self, request, queryset):
        selected_count = queryset.count()
        eligible_count = queryset.filter(
            status='shortlisted',
        ).exclude(
            interview_email_status='sent',
        ).count()
        already_sent_count = queryset.filter(
            interview_email_status='sent',
        ).count()
        wrong_status_count = queryset.exclude(status='shortlisted').count()

        if 'confirm_acceptance_send' not in request.POST:
            context = {
                **self.admin_site.each_context(request),
                'action_to': 'acceptance',
                'opts': self.model._meta,
                'title': 'Confirm interview email invite',
                'queryset': queryset,
                'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
                'selected_count': selected_count,
                'eligible_count': eligible_count,
                'already_sent_count': already_sent_count,
                'wrong_status_count': wrong_status_count,
            }
            return TemplateResponse(
                request,
                'admin/opportunities/vacancyapplication/interview_actions.html',
                context,
            )

        result = send_interview_invitation_batch(queryset, request.user)
        level = messages.ERROR if result.failed else messages.SUCCESS
        self.message_user(
            request,
            (
                f'Interview email batch complete: {result.sent} sent, '
                f'{result.failed} failed, {result.skipped_already_sent} already sent, '
                f'{result.skipped_wrong_status} not eligible, and '
                f'{result.skipped_in_progress} already processing.'
            ),
            level=level,
        )
