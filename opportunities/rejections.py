from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from config.public_links import get_oef_social_links
from ext_libs.email_service import (EmailProviderError,
                                    send_template_email_batch)

from .models import VacancyApplication

BATCH_SIZE = 500
SENDING_TIMEOUT = timedelta(minutes=15)


@dataclass(frozen=True)
class RejectionBatchResult:
    requested: int = 0
    sent: int = 0
    failed: int = 0
    skipped_wrong_status: int = 0
    skipped_already_sent: int = 0
    skipped_in_progress: int = 0


def _first_name(full_name):
    return full_name.strip().split(maxsplit=1)[0]


def _chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _claim_applications(application_ids, batch_key):
    claimed = []
    skipped_wrong_status = 0
    skipped_already_sent = 0
    skipped_in_progress = 0
    stale_before = timezone.now() - SENDING_TIMEOUT

    with transaction.atomic():
        applications = list(
            VacancyApplication.objects.select_for_update()
            .select_related('vacancy')
            .filter(pk__in=application_ids)
            .order_by('pk')
        )
        for application in applications:
            if application.status != 'not_selected':
                skipped_wrong_status += 1
                continue
            if application.rejection_email_status == 'sent':
                skipped_already_sent += 1
                continue
            if (
                application.rejection_email_status == 'sending'
                and application.updated_at >= stale_before
            ):
                skipped_in_progress += 1
                continue

            application.rejection_email_status = 'sending'
            application.rejection_email_batch_key = batch_key
            application.rejection_email_error = ''
            application.updated_at = timezone.now()
            claimed.append(application)

        if claimed:
            VacancyApplication.objects.bulk_update(
                claimed,
                (
                    'rejection_email_status',
                    'rejection_email_batch_key',
                    'rejection_email_error',
                    'updated_at',
                ),
            )

    return (
        claimed,
        skipped_wrong_status,
        skipped_already_sent,
        skipped_in_progress,
    )


def _mark_failed(applications, batch_key, error):
    VacancyApplication.objects.filter(
        pk__in=[application.pk for application in applications],
        rejection_email_batch_key=batch_key,
        rejection_email_status='sending',
    ).update(
        rejection_email_status='failed',
        rejection_email_error=str(error)[:4000],
        updated_at=timezone.now(),
    )


def _mark_sent(applications, batch_key, message_ids, sent_by):
    sent_at = timezone.now()
    with transaction.atomic():
        locked = {
            application.pk: application
            for application in VacancyApplication.objects.select_for_update().filter(
                pk__in=[application.pk for application in applications],
                rejection_email_batch_key=batch_key,
                rejection_email_status='sending',
            )
        }
        updated = []
        for application, message_id in zip(applications, message_ids):
            locked_application = locked.get(application.pk)
            if locked_application is None:
                continue
            locked_application.rejection_email_status = 'sent'
            locked_application.rejection_email_message_id = str(message_id)
            locked_application.rejection_email_sent_at = sent_at
            locked_application.rejection_email_sent_by = sent_by
            locked_application.rejection_email_error = ''
            locked_application.updated_at = sent_at
            updated.append(locked_application)

        if updated:
            VacancyApplication.objects.bulk_update(
                updated,
                (
                    'rejection_email_status',
                    'rejection_email_message_id',
                    'rejection_email_sent_at',
                    'rejection_email_sent_by',
                    'rejection_email_error',
                    'updated_at',
                ),
            )
    return len(updated)


def send_rejection_email_batch(queryset, sent_by):
    application_ids = list(queryset.order_by('pk').values_list('pk', flat=True))
    totals = {
        'requested': len(application_ids),
        'sent': 0,
        'failed': 0,
        'skipped_wrong_status': 0,
        'skipped_already_sent': 0,
        'skipped_in_progress': 0,
    }

    for application_id_chunk in _chunks(application_ids, BATCH_SIZE):
        batch_key = uuid4()
        (
            applications,
            skipped_wrong_status,
            skipped_already_sent,
            skipped_in_progress,
        ) = _claim_applications(application_id_chunk, batch_key)
        totals['skipped_wrong_status'] += skipped_wrong_status
        totals['skipped_already_sent'] += skipped_already_sent
        totals['skipped_in_progress'] += skipped_in_progress
        if not applications:
            continue

        social_links = get_oef_social_links()
        message_versions = [
            {
                'to': [
                    {
                        'email': application.email,
                        'name': application.full_name,
                    }
                ],
                'params': {
                    'first_name': _first_name(application.full_name),
                    'role_title': application.vacancy.title,
                    **social_links,
                },
            }
            for application in applications
        ]
        try:
            message_ids = send_template_email_batch(
                message_versions=message_versions,
                template_id=settings.BREVO_REJECTION_TEMPLATE_ID,
                idempotency_key=batch_key,
            )
        except EmailProviderError as error:
            _mark_failed(applications, batch_key, error)
            totals['failed'] += len(applications)
            continue

        totals['sent'] += _mark_sent(
            applications,
            batch_key,
            message_ids,
            sent_by,
        )

    return RejectionBatchResult(**totals)
