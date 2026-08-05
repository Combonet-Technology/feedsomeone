from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ext_libs.email_service import EmailProviderError, send_template_email

from .models import VacancyApplication, VolunteerOnboarding

ELIGIBLE_APPLICATION_STATUSES = {'onboarding', 'active'}


class OnboardingEmailError(Exception):
    pass


class OnboardingEmailNotEligible(OnboardingEmailError):
    pass


class OnboardingEmailInProgress(OnboardingEmailError):
    pass


class OnboardingEmailStateChanged(OnboardingEmailError):
    pass


def _first_name(full_name):
    return full_name.strip().split(maxsplit=1)[0]


def _mark_delivery_failed(onboarding_id, error):
    VolunteerOnboarding.objects.filter(pk=onboarding_id).update(
        delivery_status='failed',
        delivery_error=str(error)[:4000],
        updated_at=timezone.now(),
    )


def send_onboarding_email(application, sent_by, expected_send_count):
    if not settings.OEF_SLACK_INVITE_URL:
        raise EmailProviderError('OEF_SLACK_INVITE_URL is not configured')

    with transaction.atomic():
        application = (
            VacancyApplication.objects.select_for_update()
            .select_related('vacancy')
            .get(pk=application.pk)
        )
        if application.status not in ELIGIBLE_APPLICATION_STATUSES:
            raise OnboardingEmailNotEligible(
                'Set the application status to Onboarding before sending this email.'
            )

        onboarding = (
            VolunteerOnboarding.objects.select_for_update()
            .filter(application=application)
            .first()
        )
        if onboarding is None:
            onboarding = VolunteerOnboarding(application=application)

        recently_started = (
            onboarding.pk
            and onboarding.delivery_status == 'sending'
            and onboarding.updated_at >= timezone.now() - timedelta(minutes=15)
        )
        if recently_started:
            raise OnboardingEmailInProgress(
                'This onboarding email is already being processed.'
            )
        if onboarding.send_count != expected_send_count:
            raise OnboardingEmailStateChanged(
                'The onboarding email history changed after this confirmation page '
                'was opened. Refresh the application before sending again.'
            )

        if onboarding.send_count:
            onboarding.delivery_key = uuid4()
        onboarding.delivery_status = 'sending'
        onboarding.delivery_error = ''
        onboarding.save()

    try:
        message_id = send_template_email(
            destination=application.email,
            template_id=settings.BREVO_ONBOARDING_TEMPLATE_ID,
            params={
                'first_name': _first_name(application.full_name),
                'slack_invite_url': settings.OEF_SLACK_INVITE_URL,
            },
            message_headers={'Idempotency-Key': str(onboarding.delivery_key)},
        )
    except Exception as error:
        _mark_delivery_failed(onboarding.pk, error)
        raise

    sent_at = timezone.now()
    with transaction.atomic():
        onboarding = VolunteerOnboarding.objects.select_for_update().get(
            pk=onboarding.pk
        )
        onboarding.delivery_status = 'sent'
        onboarding.delivery_error = ''
        onboarding.brevo_message_id = (
            '' if message_id is True else str(message_id)
        )
        onboarding.send_count += 1
        onboarding.first_sent_at = onboarding.first_sent_at or sent_at
        onboarding.last_sent_at = sent_at
        onboarding.last_sent_by = sent_by
        onboarding.save()

    return onboarding
