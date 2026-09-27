"""Delegated, audited backend capability assignment for ongoing team members."""

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urljoin

from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from ext_libs.email_service import send_email

from .models import (BackendAccessChange, BackendAccessInvitation, Engagement,
                     TeamMember, UserProfile)

DELEGABLE_GROUPS = frozenset({
    'OEF Writers',
    'OEF Reviewers',
    'OEF Publishers',
    'Recruitment Manager',
})
INVITATION_CLAIM_TIMEOUT = timedelta(minutes=15)
STAFF_EMAIL_DOMAIN = 'oluwafemiebenezerfoundation.org'


def validate_staff_email(email):
    email = (email or '').strip().lower()
    if email.rpartition('@')[2] != STAFF_EMAIL_DOMAIN:
        raise ValidationError(f'Use the member\'s @{STAFF_EMAIL_DOMAIN} workspace email before granting access.')
    return email


@dataclass(frozen=True)
class AccessResult:
    user: UserProfile | None
    changed: bool
    invitation: BackendAccessInvitation | None


def _require_access_manager(actor):
    if not (
        actor and actor.is_authenticated and actor.is_active and actor.is_staff
        and actor.has_perm('user.manage_team_access')
    ):
        raise PermissionDenied('Team access management permission is required.')


def _group_names(user):
    return set(user.groups.values_list('name', flat=True))


def _desired_groups(member):
    desired = member.desired_backend_groups
    if not isinstance(desired, list) or any(not isinstance(name, str) for name in desired):
        raise ValidationError('Reconcile the configured capability presets.')
    if set(desired) - DELEGABLE_GROUPS:
        raise ValidationError('Configured capability presets contain a protected group.')
    return set(desired)


def _effective_permissions(group_names):
    groups = Group.objects.filter(name__in=group_names)
    if {group.name for group in groups} != set(group_names):
        raise ValidationError('A selected capability preset is not configured.')
    return sorted({
        f'{app_label}.{codename}'
        for app_label, codename in groups.values_list(
            'permissions__content_type__app_label', 'permissions__codename',
        ) if app_label and codename
    })


def _validate_target(member, actor):
    if member.user_id == actor.pk and not actor.is_superuser:
        raise PermissionDenied('Managers cannot change their own access.')
    if not member.user_id:
        return
    account = member.user
    if account.is_superuser or account.has_perm('user.manage_team_access'):
        raise PermissionDenied('Protected manager and superuser accounts use superuser administration.')
    if account.user_permissions.exists():
        raise PermissionDenied('Reconcile direct account permissions before delegation.')
    if _group_names(account) - DELEGABLE_GROUPS:
        raise PermissionDenied('Reconcile protected account groups before delegation.')


def preview_backend_access(member, actor, desired_groups):
    _require_access_manager(actor)
    desired = set(desired_groups)
    if desired - DELEGABLE_GROUPS:
        raise ValidationError('One or more selected capability groups are protected.')
    member = TeamMember.objects.select_related('user').get(pk=member.pk)
    _validate_target(member, actor)
    current = _desired_groups(member)
    return {
        'current': sorted(current),
        'requested': sorted(desired),
        'add': sorted(desired - current),
        'remove': sorted((current & DELEGABLE_GROUPS) - desired),
        'requires_account': member.user_id is None,
        'current_permissions': _effective_permissions(current),
        'requested_permissions': _effective_permissions(desired),
    }


@transaction.atomic
def set_backend_access(member, actor, desired_groups=None, *, reason, site_url, action='configure'):
    _require_access_manager(actor)
    if action not in ('configure', 'grant', 'resume', 'suspend', 'resend', 'reset'):
        raise ValidationError('Choose a valid access action.')
    member = TeamMember.objects.select_for_update().get(pk=member.pk)
    desired = _desired_groups(member) if desired_groups is None else set(desired_groups)
    if desired - DELEGABLE_GROUPS:
        raise ValidationError('One or more selected capability groups are protected.')
    if not (reason or '').strip():
        raise ValidationError('Record a reason for the access change.')

    # Lock the person row only. Joining nullable user here makes PostgreSQL
    # reject FOR UPDATE on the nullable side of the outer join.
    if member.user_id:
        member.user = UserProfile.objects.select_for_update().get(pk=member.user_id)
    _validate_target(member, actor)
    if action in ('grant', 'resume') and not Engagement.objects.filter(
        team_member=member, status=Engagement.Status.ACTIVE,
    ).exists():
        raise ValidationError('An active engagement is required before granting access.')

    account = member.user
    if account is None and action == 'grant':
        email = member.primary_email.strip().lower()
        if not email or len(email) > UserProfile._meta.get_field('email').max_length:
            raise ValidationError('A valid account-length email is needed for access.')
        if UserProfile.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email exists. Reconcile it explicitly first.')
        first_name, _, last_name = member.full_name.strip().partition(' ')
        account = UserProfile.objects.create_user(
            email=email, password=None, first_name=first_name, last_name=last_name,
        )
        member.user = account
        member.save(update_fields=('user', 'updated_at'))
    if account is None:
        raise ValidationError('Create the linked account before managing access.')
    before = _desired_groups(member)
    before_enabled = account.is_staff
    if not account.is_active:
        raise ValidationError('This account is disabled. A superuser must resolve its login state.')
    if action in ('grant', 'resume', 'resend', 'reset'):
        validate_staff_email(account.email)
    selected = list(Group.objects.filter(name__in=desired))
    if {group.name for group in selected} != desired:
        raise ValidationError('A selected capability preset is not configured.')

    enabled = before_enabled
    if action in ('grant', 'resume'):
        enabled = True
    elif action == 'suspend':
        enabled = False
    elif action in ('resend', 'reset') and not enabled:
        raise ValidationError('Resume backend access before sending a staff invitation.')
    if action not in ('configure', 'grant') and desired_groups is not None:
        # Capability changes and enabling access are separate operations.
        desired = before
        selected = list(Group.objects.filter(name__in=desired))
    if action in ('configure', 'grant', 'resume', 'suspend') and before == desired and before_enabled == enabled:
        return AccessResult(account, False, None)
    account.groups.set(selected if enabled else [])
    account.is_staff = enabled
    account.save(update_fields=('is_staff', 'date_updated'))
    member.desired_backend_groups = sorted(desired)
    if action == 'suspend':
        member.access_version += 1
    member.save(update_fields=('desired_backend_groups', 'access_version', 'updated_at'))
    BackendAccessChange.objects.create(
        user=account, team_member=member,
        action=action, before_enabled=before_enabled, after_enabled=enabled,
        before_groups=sorted(before), after_groups=sorted(desired),
        actor=actor, reason=reason.strip(),
    )

    invitation = None
    if action in ('grant', 'resend', 'reset'):
        member.access_version += 1
        member.save(update_fields=('access_version', 'updated_at'))
        invitation = BackendAccessInvitation.objects.create(
            team_member=member, user=account,
            recipient_email=account.email, access_version=member.access_version,
            reset_password=action == 'reset',
        )
        invitation_pk = invitation.pk
        transaction.on_commit(lambda: send_backend_invitation(invitation_pk, site_url))
    return AccessResult(account, True, invitation)


def invitation_is_current(invitation):
    account = invitation.user
    member = invitation.team_member
    return bool(
        account.is_active and account.is_staff
        and member.user_id == account.pk and invitation.recipient_email == account.email
        and invitation.access_version == member.access_version and not invitation.used_at
    )


def send_backend_invitation(invitation_id, site_url):
    with transaction.atomic():
        reference = BackendAccessInvitation.objects.get(pk=invitation_id)
        member = TeamMember.objects.select_for_update().get(pk=reference.team_member_id)
        account = UserProfile.objects.select_for_update().get(pk=reference.user_id)
        invitation = BackendAccessInvitation.objects.select_for_update().get(pk=invitation_id)
        invitation.team_member = member
        invitation.user = account
        if not invitation_is_current(invitation):
            return invitation
        stale_sending = (
            invitation.status == BackendAccessInvitation.Status.SENDING
            and (
                invitation.sending_started_at is None
                or invitation.sending_started_at <= timezone.now() - INVITATION_CLAIM_TIMEOUT
            )
        )
        if not stale_sending and invitation.status not in (
            BackendAccessInvitation.Status.PENDING,
            BackendAccessInvitation.Status.FAILED,
        ):
            return invitation
        invitation.status = BackendAccessInvitation.Status.SENDING
        invitation.attempts += 1
        invitation.sending_started_at = timezone.now()
        invitation.save(update_fields=('status', 'attempts', 'sending_started_at'))
        claimed_attempt = invitation.attempts
    try:
        account = invitation.user
        password_setup_required = invitation.reset_password or not account.has_usable_password()
        if password_setup_required:
            uid = urlsafe_base64_encode(force_bytes(account.pk))
            token = default_token_generator.make_token(account)
            path = reverse('member_access_activate', args=(invitation.key, uid, token))
            action_label = 'Set your password'
        else:
            path = reverse('admin:index')
            action_label = 'Open your OEF workspace'
        context = {
            'recipient_name': invitation.team_member.full_name or account.get_full_name(),
            'access_url': urljoin(f'{site_url.rstrip("/")}/', path.lstrip('/')),
            'action_label': action_label,
            'password_setup_required': password_setup_required,
        }
        message_id = send_email(
            destination=invitation.recipient_email,
            subject='Your OEF administration access',
            content=render_to_string('opportunities/email/staff_access_invitation.html', context),
            text_content=render_to_string('opportunities/email/staff_access_invitation.txt', context),
            message_headers={'idempotencyKey': str(invitation.key)},
        )
    except Exception as error:
        outcome = BackendAccessInvitation.Status.FAILED
        error_text = str(error)
        message_id = ''
    else:
        outcome = BackendAccessInvitation.Status.SENT
        error_text = ''
    with transaction.atomic():
        invitation = BackendAccessInvitation.objects.select_for_update().get(pk=invitation_id)
        if (
            invitation.status == BackendAccessInvitation.Status.SENDING
            and invitation.attempts == claimed_attempt
        ):
            invitation.status = outcome
            invitation.error = error_text
            invitation.message_id = str(message_id or '')
            invitation.sent_at = timezone.now() if outcome == BackendAccessInvitation.Status.SENT else None
            invitation.save(update_fields=(
                'status', 'error', 'message_id', 'sent_at',
            ))
    return invitation
