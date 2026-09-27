"""Personnel lifecycle actions, independent of Django login and backend access."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from opportunities.models import VacancyApplication

from .models import Engagement, TeamMember, UserProfile

APPOINTMENT_STATUSES = (
    VacancyApplication.Status.OFFER_ACCEPTED,
    VacancyApplication.Status.AGREEMENT_SIGNED,
    VacancyApplication.Status.ONBOARDING,
    VacancyApplication.Status.ACTIVE,
)


def available_appointment_applications():
    return VacancyApplication.objects.filter(
        status__in=APPOINTMENT_STATUSES, team_member__isnull=True,
        engagement__isnull=True, applicant__team_membership__isnull=True,
    ).select_related('vacancy')


def _require_engagement_manager(actor):
    if not (
        actor and actor.is_authenticated and actor.is_active and actor.is_staff
        and actor.has_perm('user.manage_team_engagement')
    ):
        raise PermissionDenied('Team engagement management permission is required.')


def _require_appointment_authority(actor):
    if not (
        actor and actor.is_authenticated and actor.is_active and actor.is_staff
        and actor.has_perm('opportunities.change_vacancyapplication')
    ):
        raise PermissionDenied('Recruitment application change permission is required.')


def _new_member_account(email, full_name):
    email = email.strip().lower()
    if not email or len(email) > UserProfile._meta.get_field('email').max_length:
        raise ValidationError('A valid account-length email is needed for a team member.')
    if UserProfile.objects.filter(email__iexact=email).exists():
        raise ValidationError('An account with this email exists. Reconcile its identity explicitly.')
    first_name, _, last_name = full_name.strip().partition(' ')
    account = UserProfile.objects.create_user(
        email=email, password=None, first_name=first_name, last_name=last_name,
    )
    # No password, staff flag or capability group is granted at appointment.
    return account


@transaction.atomic
def appoint_candidate(application, actor, *, team_member=None, start_date=None,
                      full_name=None, email=None, role_title=None, engagement_type=None):
    """Appoint an eligible candidate once, retaining the original application."""
    _require_appointment_authority(actor)
    application = VacancyApplication.objects.select_for_update().select_related(
        'vacancy',
    ).get(pk=application.pk)
    existing = Engagement.objects.select_for_update().filter(
        source_application=application,
    ).first()
    if existing:
        if (
            not application.appointed_at
            or not application.appointed_by_id
        ):
            raise ValidationError(
                'An existing engagement lacks a verified appointment record. Reconcile it explicitly.'
            )
        if application.status != VacancyApplication.Status.APPOINTED:
            application.status = VacancyApplication.Status.APPOINTED
            application.save(update_fields=('status', 'updated_at'))
        return existing

    if application.status not in APPOINTMENT_STATUSES:
        raise ValidationError('This application is not eligible for appointment.')
    email = (application.email if email is None else email).strip().lower()
    full_name = (application.full_name if full_name is None else full_name).strip()
    role_title = (application.vacancy.title if role_title is None else role_title).strip()
    engagement_type = application.vacancy.engagement_type if engagement_type is None else engagement_type
    if not full_name:
        raise ValidationError('The application needs a full name before appointment.')
    if not role_title or len(role_title) > 255:
        raise ValidationError('A valid role title is required.')
    if engagement_type not in dict(TeamMember.ENGAGEMENT_TYPE_CHOICES):
        raise ValidationError('Choose a valid engagement type.')
    UserProfile._meta.get_field('email').clean(email, None)

    member = None
    if team_member is not None:
        member = TeamMember.objects.select_for_update().get(pk=team_member.pk)
        if member.source_application_id not in (None, application.pk):
            raise ValidationError('The selected person is linked to another application.')
    else:
        member = TeamMember.objects.select_for_update().filter(
            source_application=application,
        ).first()
    if member is None and application.applicant_id:
        member = TeamMember.objects.select_for_update().filter(user_id=application.applicant_id).first()

    if member is None:
        matches = TeamMember.objects.filter(primary_email__iexact=email)
        if matches.exists():
            raise ValidationError(
                'A person with this email already exists. Select that person explicitly '
                'or reconcile the identity before appointment.'
            )
    elif member.primary_email and member.primary_email.strip().lower() != email:
        raise ValidationError('The existing team member email conflicts with the application.')

    account = member.user if member and member.user_id else None
    if account is None and application.applicant_id:
        account = UserProfile.objects.select_for_update().get(pk=application.applicant_id)
    if account is not None:
        if (account.email or '').strip().lower() != email:
            raise ValidationError('The applicant account email conflicts with the application.')
        if member and member.user_id and application.applicant_id and member.user_id != application.applicant_id:
            raise ValidationError('The existing team member is linked to another applicant account.')
    else:
        account = _new_member_account(email, full_name)

    if member is None:
        member = TeamMember.objects.create(
            user=account, full_name=full_name, primary_email=email, source_application=application,
        )
    else:
        updates = []
        if not member.user_id:
            member.user = account
            updates.append('user')
        if not member.full_name:
            member.full_name = full_name
            updates.append('full_name')
        if not member.primary_email:
            member.primary_email = email
            updates.append('primary_email')
        if not member.source_application_id:
            member.source_application = application
            updates.append('source_application')
        if updates:
            member.save(update_fields=(*updates, 'updated_at'))

    if start_date is None:
        start_date = application.volunteer_offer.start_date if hasattr(application, 'volunteer_offer') else None

    now = timezone.now()
    _replace_current_engagements(member, actor, replace_current=False)
    engagement = Engagement.objects.create(
        team_member=member,
        source_application=application,
        role_title=role_title,
        engagement_type=engagement_type,
        status=Engagement.Status.ACTIVE,
        start_date=start_date,
    )
    application.status = VacancyApplication.Status.APPOINTED
    application.applicant = account
    application.appointed_at = now
    application.appointed_by = actor
    application.save(update_fields=(
        'status', 'applicant', 'appointed_at', 'appointed_by', 'updated_at',
    ))
    return engagement


@transaction.atomic
def start_direct_engagement(member, actor, *, role_title, engagement_type, start_date=None,
                            replace_current=False, status=Engagement.Status.ACTIVE):
    _require_engagement_manager(actor)
    member = TeamMember.objects.select_for_update().get(pk=member.pk)
    if not role_title.strip():
        raise ValidationError('A role title is required.')
    if engagement_type not in dict(TeamMember.ENGAGEMENT_TYPE_CHOICES):
        raise ValidationError('Choose a valid engagement type.')
    if not member.full_name.strip():
        raise ValidationError('A full name is required.')
    if status not in (Engagement.Status.ONBOARDING, Engagement.Status.ACTIVE):
        raise ValidationError('A new engagement must be onboarding or active.')
    _replace_current_engagements(member, actor, replace_current=replace_current)
    if not member.user_id:
        member.user = _new_member_account(member.primary_email, member.full_name)
        member.save(update_fields=('user', 'updated_at'))
    return Engagement.objects.create(
        team_member=member,
        role_title=role_title.strip(),
        engagement_type=engagement_type,
        status=status,
        start_date=start_date,
    )


@transaction.atomic
def complete_onboarding(engagement, actor):
    _require_engagement_manager(actor)
    TeamMember.objects.select_for_update().get(pk=engagement.team_member_id)
    engagement = Engagement.objects.select_for_update().get(pk=engagement.pk)
    if engagement.onboarding_status == Engagement.OnboardingStatus.COMPLETED:
        return engagement
    if engagement.status == Engagement.Status.ENDED:
        raise ValidationError('Ended engagements cannot complete onboarding.')
    now = timezone.now()
    engagement.onboarding_status = Engagement.OnboardingStatus.COMPLETED
    engagement.onboarding_completed_at = now
    engagement.onboarding_completed_by = actor
    engagement.status = Engagement.Status.ACTIVE
    engagement.save(update_fields=(
        'onboarding_status', 'onboarding_completed_at', 'onboarding_completed_by',
        'status', 'updated_at',
    ))
    if engagement.source_application_id:
        VacancyApplication.objects.filter(pk=engagement.source_application_id).update(
            onboarding_completed_at=now, onboarding_completed_by=actor,
        )
    return engagement


def _replace_current_engagements(member, actor, *, replace_current):
    current = list(member.engagements.select_for_update().exclude(status=Engagement.Status.ENDED))
    if len(current) > 1:
        raise ValidationError('Multiple current engagements exist. Reconcile them before adding another.')
    if current and not replace_current:
        raise ValidationError('End the current engagement first or confirm its replacement.')
    for engagement in current:
        end_engagement(engagement, actor)
        # The replacement is created in this same transaction, with no access gap.
        Engagement.objects.filter(pk=engagement.pk).update(access_review_required=False)


@transaction.atomic
def update_engagement(engagement, actor, *, role_title, engagement_type, start_date, end_date, status):
    _require_engagement_manager(actor)
    TeamMember.objects.select_for_update().get(pk=engagement.team_member_id)
    engagement = Engagement.objects.select_for_update().get(pk=engagement.pk)
    previous_status = engagement.status
    if previous_status == Engagement.Status.ENDED and status != previous_status:
        raise ValidationError('An ended engagement cannot be restarted. Add a new engagement.')
    engagement.role_title = role_title.strip()
    engagement.engagement_type = engagement_type
    engagement.start_date = start_date
    engagement.end_date = end_date
    engagement.status = status
    if status == Engagement.Status.ENDED:
        engagement.end_date = end_date or engagement.end_date or timezone.localdate()
    engagement.full_clean()
    if status == Engagement.Status.ENDED and previous_status != status:
        return _record_engagement_end(engagement, actor, engagement.end_date)
    engagement.save()
    return engagement


def _record_engagement_end(engagement, actor, end_date):
    engagement.status = Engagement.Status.ENDED
    engagement.end_date = end_date or timezone.localdate()
    engagement.clean()
    engagement.ended_at = timezone.now()
    engagement.ended_by = actor
    other_current = Engagement.objects.filter(
        team_member_id=engagement.team_member_id,
    ).exclude(pk=engagement.pk).exclude(status=Engagement.Status.ENDED).exists()
    account = engagement.team_member.user
    engagement.access_review_required = bool(account and account.is_staff and not other_current)
    engagement.save()
    return engagement


@transaction.atomic
def end_engagement(engagement, actor, *, end_date=None):
    _require_engagement_manager(actor)
    TeamMember.objects.select_for_update().get(pk=engagement.team_member_id)
    engagement = Engagement.objects.select_for_update().get(pk=engagement.pk)
    if engagement.status == Engagement.Status.ENDED:
        return engagement
    return _record_engagement_end(engagement, actor, end_date)
