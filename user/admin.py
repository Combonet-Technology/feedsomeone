from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import AdminDateWidget
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.http import urlencode

from opportunities.models import VacancyApplication
from user.access import (DELEGABLE_GROUPS, preview_backend_access,
                         send_backend_invitation, set_backend_access)
from user.forms import UserProfileAdminChangeForm, UserProfileAdminCreationForm
from user.models import (BackendAccessChange, BackendAccessInvitation,
                         Engagement, TeamMember, UserProfile, Volunteer)
from user.workforce import (appoint_candidate,
                            available_appointment_applications,
                            complete_onboarding, end_engagement,
                            start_direct_engagement, update_engagement)


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

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

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
    class MemberForm(forms.ModelForm):
        actor = None
        appointment_error = None
        application = forms.ModelChoiceField(
            queryset=VacancyApplication.objects.none(), required=False,
            label='Vacancy application', empty_label='Enter details manually',
        )
        role_title = forms.CharField(max_length=255, label='Initial role title')
        engagement_type = forms.ChoiceField(
            choices=TeamMember.ENGAGEMENT_TYPE_CHOICES, label='Engagement type',
        )
        start_date = forms.DateField(
            required=False, widget=AdminDateWidget,
            help_text='Effective start date (YYYY-MM-DD). Leave blank if not yet agreed.',
        )

        class Meta:
            model = TeamMember
            fields = ('full_name', 'primary_email')

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if 'application' in self.fields:
                if self.instance.pk:
                    self.fields.pop('application')
                elif self.actor and self.actor.has_perm('opportunities.change_vacancyapplication'):
                    self.fields['application'].queryset = available_appointment_applications()
                    self.fields['application'].widget.attrs['data-preview-url'] = reverse(
                        'admin:user_teammember_application_preview',
                    )
            if self.instance.pk:
                self.fields['role_title'].required = False
                self.fields['engagement_type'].required = False

        def clean_full_name(self):
            value = self.cleaned_data['full_name'].strip()
            if not value:
                raise forms.ValidationError('A full name is required.')
            return value

        def clean_primary_email(self):
            value = self.cleaned_data['primary_email'].strip().lower()
            if not value:
                raise forms.ValidationError('An email is required.')
            if len(value) > UserProfile._meta.get_field('email').max_length:
                raise forms.ValidationError('This email is too long for a team account.')
            if TeamMember.objects.filter(primary_email__iexact=value).exclude(
                pk=self.instance.pk,
            ).exists():
                raise forms.ValidationError(
                    'A person with this email already exists. Open that record or reconcile the identity.'
                )
            application = self.cleaned_data.get('application')
            accounts = UserProfile.objects.filter(email__iexact=value)
            if application and application.applicant_id:
                if application.applicant.email.strip().lower() != value:
                    raise forms.ValidationError('The applicant account email cannot be changed here.')
                accounts = accounts.exclude(pk=application.applicant_id)
            if not self.instance.pk and accounts.exists():
                raise forms.ValidationError(
                    'A login account with this email already exists. '
                    'Reconcile its identity before creating a team member.'
                )
            return value

        def clean(self):
            cleaned = super().clean()
            if self.appointment_error:
                raise forms.ValidationError(self.appointment_error)
            return cleaned

        class Media:
            js = ('user/team_member_application.js',)

    form = MemberForm
    list_display = ('full_name', 'primary_email', 'engagement_summary', 'access_badge')
    search_fields = ('full_name', 'primary_email', 'user__email')
    readonly_fields = (
        'user', 'engagement_summary', 'engagement_link', 'access_badge', 'access_link', 'application_link',
    )

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)

        class RequestMemberForm(base_form):
            actor = request.user
            appointment_error = getattr(request, '_appointment_error', None)

        return RequestMemberForm

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            with transaction.atomic():
                return super().changeform_view(request, object_id, form_url, extra_context)
        except ValidationError as error:
            # Roll back a stale/conflicting appointment, then show the bound form.
            request._appointment_error = error.messages
            return super().changeform_view(request, object_id, form_url, extra_context)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, 'primary_email') if obj else fields

    def get_fields(self, request, obj=None):
        if obj is None:
            return ('application', 'full_name', 'primary_email', 'role_title', 'engagement_type', 'start_date')
        fields = (
            'full_name', 'primary_email', 'user', 'engagement_summary',
            'access_badge', 'application_link',
        )
        if self._can_manage_engagement(request):
            fields += ('engagement_link',)
        if self._can_manage_access(request):
            fields += ('access_link',)
        return fields

    @admin.display(description='Vacancy application')
    def application_link(self, obj):
        application_id = obj.source_application_id
        if not application_id:
            sources = list(obj.engagements.exclude(source_application=None).values_list(
                'source_application_id', flat=True,
            )[:2])
            if len(sources) > 1:
                return 'Multiple vacancy applications exist. Review the engagement history.'
            application_id = sources[0] if sources else None
        if not application_id:
            return 'No vacancy application exists for this team member.'
        return format_html(
            '<a href="{}">View vacancy application</a>',
            reverse('admin:opportunities_vacancyapplication_change', args=(application_id,)),
        )

    def application_preview(self, request):
        if not (
            self.has_add_permission(request)
            and request.user.has_perm('opportunities.change_vacancyapplication')
        ):
            raise PermissionDenied
        application_id = request.GET.get('application', '')
        if not application_id.isdecimal():
            raise Http404
        application = get_object_or_404(
            available_appointment_applications(), pk=application_id,
        )
        response = JsonResponse({
            'full_name': application.full_name,
            'primary_email': application.email,
            'role_title': application.vacancy.title,
            'engagement_type': application.vacancy.engagement_type,
        })
        response['Cache-Control'] = 'no-store'
        return response

    def get_queryset(self, request):
        # Legacy access rows without an engagement are not confirmed membership.
        return super().get_queryset(request).filter(engagements__isnull=False).distinct()

    @admin.display(description='Engagements')
    def engagement_summary(self, obj):
        return obj.engagements.filter(status='active').values_list('role_title', flat=True).first()

    @admin.display(description='Manage engagements')
    def engagement_link(self, obj):
        if not obj.pk:
            return ''
        list_url = reverse('admin:user_engagement_changelist')
        return format_html(
            '<a href="{}?{}">View engagements</a>',
            list_url, urlencode({'team_member__id__exact': obj.pk}),
        )

    @admin.display(description='Permissions')
    def access_badge(self, obj):
        if not obj.user_id:
            return 'No account'
        if not obj.user.is_staff:
            return 'No staff access'
        return ', '.join(sorted(obj.user.groups.values_list('name', flat=True))) or 'Staff flag only'

    @admin.display(description='Manage permissions')
    def access_link(self, obj):
        if not obj.pk:
            return ''
        return format_html(
            '<a href="{}">Manage permissions</a>',
            reverse('admin:user_teammember_access', args=(obj.pk,)),
        )

    def get_urls(self):
        return [
            path(
                'application-preview/', self.admin_site.admin_view(self.application_preview),
                name='user_teammember_application_preview',
            ),
            path(
                '<path:object_id>/access/',
                self.admin_site.admin_view(self.manage_access_view),
                name='user_teammember_access',
            ),
        ] + super().get_urls()

    def manage_access_view(self, request, object_id):
        if not self._can_manage_access(request):
            raise PermissionDenied
        member = self.get_object(request, object_id)
        if member is None:
            raise PermissionDenied
        if request.method == 'POST' and 'retry_invitation' in request.POST:
            if not request.POST['retry_invitation'].isdecimal():
                raise PermissionDenied
            invitation = BackendAccessInvitation.objects.filter(
                pk=request.POST['retry_invitation'], team_member=member,
                user_id=member.user_id,
            ).first()
            if (
                invitation is None or not member.user_id
                or not member.user.is_active or not member.user.is_staff
            ):
                raise PermissionDenied
            send_backend_invitation(invitation.pk, request.build_absolute_uri('/'))
            return HttpResponseRedirect(request.path)
        current = list(member.user.groups.values_list('name', flat=True)) if member.user_id else []
        form = TeamAccessForm(
            request.POST or None,
            initial={'groups': current},
        )
        preview = None
        if request.method == 'POST' and form.is_valid():
            selected = form.cleaned_data['groups']
            try:
                preview = preview_backend_access(member, request.user, selected)
                if 'confirm' in request.POST:
                    result = set_backend_access(
                        member, request.user, selected,
                        reason=form.cleaned_data['reason'],
                        site_url=request.build_absolute_uri('/'),
                    )
                    self.message_user(
                        request,
                        'Backend access updated. Invitation delivery is recorded separately.'
                        if result.changed else 'Backend access already matched the selection.',
                        messages.SUCCESS,
                    )
                    return HttpResponseRedirect(reverse('admin:user_teammember_change', args=(member.pk,)))
            except (PermissionDenied, ValidationError) as error:
                form.add_error(None, error)
        return TemplateResponse(request, 'admin/user/team_access.html', {
            **self.admin_site.each_context(request),
            'title': f'Manage backend access: {member}',
            'opts': self.model._meta,
            'member': member,
            'form': form,
            'preview': preview,
            'access_changes': BackendAccessChange.objects.filter(
                team_member=member,
            ).select_related('actor'),
            'access_invitations': BackendAccessInvitation.objects.filter(team_member=member),
            'change_url': reverse('admin:user_teammember_change', args=(member.pk,)),
        })

    @staticmethod
    def _can_manage_access(request):
        return (
            request.user.is_active and request.user.is_staff
            and request.user.has_perm('user.manage_team_access')
        )

    @staticmethod
    def _can_manage_engagement(request):
        return (
            request.user.is_active and request.user.is_staff
            and request.user.has_perm('user.manage_team_engagement')
        )

    def has_module_permission(self, request):
        return self._can_manage_access(request) or self._can_manage_engagement(request)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self._can_manage_engagement(request)

    def has_change_permission(self, request, obj=None):
        return self._can_manage_engagement(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        application = form.cleaned_data.get('application') if not change else None
        if application:
            engagement = appoint_candidate(
                application, request.user, full_name=obj.full_name, email=obj.primary_email,
                role_title=form.cleaned_data['role_title'],
                engagement_type=form.cleaned_data['engagement_type'],
                start_date=form.cleaned_data.get('start_date'),
            )
            obj.pk = engagement.team_member_id
            obj.refresh_from_db()
            return
        super().save_model(request, obj, form, change)
        if not change:
            start_direct_engagement(
                obj, request.user, role_title=form.cleaned_data['role_title'],
                engagement_type=form.cleaned_data['engagement_type'],
                start_date=form.cleaned_data.get('start_date'),
            )


class TeamAccessForm(forms.Form):
    groups = forms.MultipleChoiceField(
        choices=tuple((name, name) for name in sorted(DELEGABLE_GROUPS)),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Capability presets',
    )
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label='Reason')


@admin.register(Engagement)
class EngagementAdmin(admin.ModelAdmin):
    class EngagementForm(forms.ModelForm):
        replace_current = forms.BooleanField(
            required=False, label='End the current engagement and replace it',
            help_text=(
                'Ends the current engagement today and creates a new history record. Backend access is unchanged.'
            ),
        )
        lifecycle_error = None

        class Meta:
            model = Engagement
            fields = ('team_member', 'role_title', 'engagement_type', 'start_date', 'end_date', 'status')

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if not self.instance.pk:
                self.fields['status'].choices = [
                    choice for choice in Engagement.Status.choices if choice[0] != Engagement.Status.ENDED
                ]

        def clean(self):
            cleaned = super().clean()
            if self.lifecycle_error:
                raise forms.ValidationError(self.lifecycle_error)
            member = cleaned.get('team_member', self.instance.team_member if self.instance.pk else None)
            if not self.instance.pk and member and member.engagements.exclude(status='ended').exists():
                if not cleaned.get('replace_current'):
                    raise forms.ValidationError('End the current engagement first or confirm its replacement.')
            return cleaned

        def _get_validation_exclusions(self):
            exclude = super()._get_validation_exclusions()
            if not self.instance.pk:
                # ModelChoiceField validates the member; the service and DB enforce
                # uniqueness after an explicitly confirmed replacement has ended.
                exclude.add('team_member')
            return exclude

    form = EngagementForm
    list_display = (
        'team_member', 'role_title', 'engagement_type', 'status',
        'start_date', 'end_date', 'onboarding_status', 'access_review_required',
    )
    list_filter = ('status', 'onboarding_status', 'engagement_type', 'access_review_required')
    search_fields = ('team_member__full_name', 'team_member__primary_email', 'role_title')
    actions = ('complete_selected_onboarding', 'end_selected_engagements')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'team_member':
            kwargs['queryset'] = TeamMember.objects.filter(engagements__isnull=False).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return ('team_member', 'role_title', 'engagement_type', 'start_date', 'status', 'replace_current')
        return (
            'team_member', 'role_title', 'engagement_type', 'status',
            'onboarding_status', 'onboarding_started_at', 'onboarding_completed_at',
            'onboarding_completed_by', 'start_date', 'end_date', 'ended_at',
            'ended_by', 'access_review_required', 'source_application', 'created_at', 'updated_at',
        )

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        editable = {'role_title', 'engagement_type', 'start_date', 'end_date'}
        if obj.status != Engagement.Status.ENDED:
            editable.add('status')
        return tuple(field for field in self.get_fields(request, obj) if field not in editable)

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)

        class RequestEngagementForm(base_form):
            lifecycle_error = getattr(request, '_engagement_error', None)

        return RequestEngagementForm

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            with transaction.atomic():
                return super().changeform_view(request, object_id, form_url, extra_context)
        except (ValidationError, IntegrityError) as error:
            if isinstance(error, IntegrityError):
                if getattr(getattr(error.__cause__, 'diag', None), 'constraint_name', None) != (
                    'one_current_engagement_per_member'
                ):
                    raise
                request._engagement_error = ['A current engagement already exists. Reload and review it.']
            else:
                request._engagement_error = error.messages
            return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if change:
            saved = update_engagement(
                obj, request.user, role_title=obj.role_title, engagement_type=obj.engagement_type,
                start_date=obj.start_date, end_date=obj.end_date, status=obj.status,
            )
        else:
            saved = start_direct_engagement(
                obj.team_member, request.user, role_title=obj.role_title,
                engagement_type=obj.engagement_type, start_date=obj.start_date, status=obj.status,
                replace_current=form.cleaned_data['replace_current'],
            )
        obj.pk = saved.pk
        obj.refresh_from_db()
        if obj.access_review_required:
            self.message_user(request, 'Review backend access for this ended engagement.', messages.WARNING)

    def has_module_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        return TeamMemberAdmin._can_manage_engagement(request)

    def has_add_permission(self, request):
        return TeamMemberAdmin._can_manage_engagement(request)

    def has_change_permission(self, request, obj=None):
        return TeamMemberAdmin._can_manage_engagement(request)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Complete onboarding for selected engagements')
    def complete_selected_onboarding(self, request, queryset):
        for engagement in queryset:
            try:
                complete_onboarding(engagement, request.user)
            except ValidationError as error:
                self.message_user(request, str(error), messages.ERROR)

    @admin.action(description='End selected engagements')
    def end_selected_engagements(self, request, queryset):
        for engagement in queryset:
            try:
                ended = end_engagement(engagement, request.user)
            except ValidationError as error:
                self.message_user(request, str(error), messages.ERROR)
                continue
            if ended.access_review_required:
                self.message_user(
                    request,
                    f'{ended.team_member} still has backend access. Review and suspend it.',
                    messages.WARNING,
                )
