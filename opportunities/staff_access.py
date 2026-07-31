from dataclasses import dataclass
from urllib.parse import urljoin

from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from ext_libs.email_service import send_email
from user.models import TeamMember, UserProfile

from .models import VacancyApplication

RECRUITMENT_MANAGER_GROUP = 'Recruitment Manager'
ELIGIBLE_APPLICATION_STATUSES = {
    'agreement_signed',
    'onboarding',
    'active',
}


class StaffAccessError(Exception):
    pass


class StaffAccessConflict(StaffAccessError):
    pass


class StaffAccessNotEligible(StaffAccessError):
    pass


@dataclass(frozen=True)
class StaffAccessResult:
    team_member: TeamMember
    account_created: bool
    password_setup_required: bool


def _require_superuser(user):
    if not user or not user.is_authenticated or not user.is_superuser:
        raise StaffAccessError('Only a superuser can manage staff access.')


def _split_name(full_name):
    parts = full_name.strip().split(maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else ''


def _absolute_url(site_url, route_name, *args):
    path = reverse(route_name, args=args)
    return urljoin(f'{site_url.rstrip("/")}/', path.lstrip('/'))


def _resolve_user(application):
    email = application.email.strip().lower()
    if len(email) > UserProfile._meta.get_field('email').max_length:
        raise StaffAccessConflict(
            'The applicant email is longer than the current user-account limit.'
        )

    if application.applicant_id:
        user = application.applicant
        if user.email.lower() != email:
            raise StaffAccessConflict(
                'The linked user account does not match the application email.'
            )
        return user, False

    user = UserProfile.objects.filter(email__iexact=email).first()
    if user:
        return user, False

    first_name, last_name = _split_name(application.full_name)
    user = UserProfile.objects.create_user(
        email=email,
        password=None,
        first_name=first_name,
        last_name=last_name,
    )
    return user, True


def _resolve_team_member(application, user):
    application_member = TeamMember.objects.filter(source_application=application).first()
    user_member = TeamMember.objects.filter(user=user).first()
    if application_member and application_member.user_id != user.pk:
        raise StaffAccessConflict(
            'This application is already connected to a different team member.'
        )
    if user_member and user_member.source_application_id not in (None, application.pk):
        raise StaffAccessConflict(
            'This user already has a team-member record from another application.'
        )
    return application_member or user_member


def grant_staff_access(application, form_data, granted_by, site_url):
    _require_superuser(granted_by)

    with transaction.atomic():
        application = (
            VacancyApplication.objects.select_for_update()
            .select_related('vacancy')
            .get(pk=application.pk)
        )
        if application.status not in ELIGIBLE_APPLICATION_STATUSES:
            raise StaffAccessNotEligible(
                'The volunteer agreement must be signed before staff access is granted.'
            )

        user, account_created = _resolve_user(application)
        password_setup_required = not user.has_usable_password()
        first_name, last_name = _split_name(application.full_name)
        changed_user_fields = []
        if not user.first_name:
            user.first_name = first_name
            changed_user_fields.append('first_name')
        if not user.last_name:
            user.last_name = last_name
            changed_user_fields.append('last_name')
        if not user.is_active:
            user.is_active = True
            changed_user_fields.append('is_active')
        if not user.is_staff:
            user.is_staff = True
            changed_user_fields.append('is_staff')
        if changed_user_fields:
            user.save(update_fields=(*changed_user_fields, 'date_updated'))

        try:
            group = Group.objects.get(name=RECRUITMENT_MANAGER_GROUP)
        except Group.DoesNotExist as error:
            raise StaffAccessError(
                'The Recruitment Manager permission group is not configured.'
            ) from error
        user.groups.add(group)

        if application.applicant_id != user.pk:
            application.applicant = user
            application.save(update_fields=('applicant', 'updated_at'))

        team_member = _resolve_team_member(application, user)
        member_values = {
            'source_application': application,
            'role_title': form_data['role_title'],
            'engagement_type': form_data['engagement_type'],
            'start_date': form_data.get('start_date'),
            'status': 'invited' if password_setup_required else 'onboarding',
            'access_granted_at': timezone.now(),
            'access_granted_by': granted_by,
            'access_revoked_at': None,
            'access_revoked_by': None,
            'invitation_error': '',
        }
        if team_member:
            for field, value in member_values.items():
                setattr(team_member, field, value)
            team_member.save()
        else:
            team_member = TeamMember.objects.create(user=user, **member_values)

    if password_setup_required:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        access_url = _absolute_url(site_url, 'staff_access_activate', uid, token)
        action_label = 'Set your password'
    else:
        access_url = _absolute_url(site_url, 'admin:index')
        action_label = 'Open the OEF administration workspace'

    context = {
        'recipient_name': application.full_name,
        'role_title': form_data['role_title'],
        'access_url': access_url,
        'action_label': action_label,
        'password_setup_required': password_setup_required,
    }
    try:
        message_id = send_email(
            destination=user.email,
            subject='Your OEF administration access',
            content=render_to_string('opportunities/email/staff_access_invitation.html', context),
            text_content=render_to_string(
                'opportunities/email/staff_access_invitation.txt',
                context,
            ),
        )
    except Exception as error:
        TeamMember.objects.filter(pk=team_member.pk).update(
            invitation_error=str(error),
        )
        raise

    TeamMember.objects.filter(pk=team_member.pk).update(
        invitation_sent_at=timezone.now(),
        invitation_message_id=str(message_id or ''),
        invitation_error='',
    )
    team_member.refresh_from_db()
    return StaffAccessResult(
        team_member=team_member,
        account_created=account_created,
        password_setup_required=password_setup_required,
    )


def revoke_staff_access(application, revoked_by):
    _require_superuser(revoked_by)

    with transaction.atomic():
        team_member = (
            TeamMember.objects.select_for_update()
            .select_related('user')
            .filter(source_application=application)
            .first()
        )
        if not team_member:
            raise StaffAccessError('No team-member access exists for this application.')

        user = team_member.user
        group = Group.objects.filter(name=RECRUITMENT_MANAGER_GROUP).first()
        if group:
            user.groups.remove(group)
        if not user.is_superuser and not user.groups.exists() and not user.user_permissions.exists():
            user.is_staff = False
            user.save(update_fields=('is_staff', 'date_updated'))

        team_member.status = 'inactive'
        team_member.access_revoked_at = timezone.now()
        team_member.access_revoked_by = revoked_by
        team_member.save(
            update_fields=(
                'status',
                'access_revoked_at',
                'access_revoked_by',
                'updated_at',
            )
        )
        return team_member


def mark_staff_invitation_accepted(user):
    return TeamMember.objects.filter(user=user, status='invited').update(
        status='onboarding',
        activated_at=timezone.now(),
    )
