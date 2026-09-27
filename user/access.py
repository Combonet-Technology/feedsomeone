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
    current = _group_names(member.user) if member.user_id else set()
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
def set_backend_access(member, actor, desired_groups, *, reason, site_url):
    _require_access_manager(actor)
    desired = set(desired_groups)
    if desired - DELEGABLE_GROUPS:
        raise ValidationError('One or more selected capability groups are protected.')
    if not (reason or '').strip():
        raise ValidationError('Record a reason for the access change.')

    # Lock the person row only. Joining nullable user here makes PostgreSQL
    # reject FOR UPDATE on the nullable side of the outer join.
    member = TeamMember.objects.select_for_update().get(pk=member.pk)
    _validate_target(member, actor)
    if desired and not Engagement.objects.filter(
        team_member=member, status=Engagement.Status.ACTIVE,
    ).exists():
        raise ValidationError('An active engagement is required before granting access.')

    account_created = False
    account = member.user
    if account is None and desired:
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
        account_created = True

    if account is None:
        return AccessResult(None, False, None)
    account = UserProfile.objects.select_for_update().get(pk=account.pk)
    before = _group_names(account)
    if not account.is_active:
        raise ValidationError('This account is disabled. A superuser must resolve its login state.')
    selected = list(Group.objects.filter(name__in=desired))
    if {group.name for group in selected} != desired:
        raise ValidationError('A selected capability preset is not configured.')

    if before == desired and account.is_staff == bool(desired):
        return AccessResult(account, False, None)

    account.groups.set(selected)
    account.is_staff = bool(desired)
    account.save(update_fields=('is_staff', 'date_updated'))
    BackendAccessChange.objects.create(
        user=account, team_member=member,
        action='grant_or_update' if desired else 'suspend',
        before_groups=sorted(before), after_groups=sorted(desired),
        actor=actor, reason=reason.strip(),
    )

    invitation = None
    if desired and (account_created or desired - before):
        invitation = BackendAccessInvitation.objects.create(
            team_member=member, user=account,
        )
        invitation_pk = invitation.pk
        transaction.on_commit(lambda: send_backend_invitation(invitation_pk, site_url))
    return AccessResult(account, True, invitation)


def send_backend_invitation(invitation_id, site_url):
    with transaction.atomic():
        invitation = BackendAccessInvitation.objects.select_for_update().select_related(
            'user', 'team_member',
        ).get(pk=invitation_id)
        if (
            not invitation.user.is_active or not invitation.user.is_staff
            or invitation.team_member.user_id != invitation.user_id
        ):
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
        password_setup_required = not account.has_usable_password()
        if password_setup_required:
            uid = urlsafe_base64_encode(force_bytes(account.pk))
            token = default_token_generator.make_token(account)
            path = reverse('staff_access_activate', args=(uid, token))
            action_label = 'Set your password'
        else:
            path = reverse('admin:index')
            action_label = 'Open the OEF administration workspace'
        context = {
            'recipient_name': invitation.team_member.full_name or account.get_full_name(),
            'role_title': invitation.team_member.engagements.filter(
                status=Engagement.Status.ACTIVE,
            ).values_list('role_title', flat=True).first(),
            'access_url': urljoin(f'{site_url.rstrip("/")}/', path.lstrip('/')),
            'action_label': action_label,
            'password_setup_required': password_setup_required,
        }
        message_id = send_email(
            destination=account.email,
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
