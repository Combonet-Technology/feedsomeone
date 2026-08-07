from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from .models import VacancyApplication

BATCH_SIZE = 500
SENDING_TIMEOUT = timedelta(minutes=15)


@dataclass(frozen=True)
class ApplicationEmailBatchResult:
    requested: int = 0
    sent: int = 0
    failed: int = 0
    skipped_wrong_status: int = 0
    skipped_already_sent: int = 0
    skipped_in_progress: int = 0


@dataclass(frozen=True)
class ApplicationEmailBatchConfig:
    eligible_statuses: frozenset
    delivery_status_field: str
    batch_key_field: str
    message_id_field: str
    sent_at_field: str
    sent_by_field: str
    error_field: str
    template_id: int
    params_builder: object
    send_batch: object


def first_name(full_name):
    return full_name.strip().split(maxsplit=1)[0]


def _chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _claim_applications(application_ids, batch_key, config):
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
            if application.status not in config.eligible_statuses:
                skipped_wrong_status += 1
                continue
            delivery_status = getattr(
                application,
                config.delivery_status_field,
            )
            if delivery_status == 'sent':
                skipped_already_sent += 1
                continue
            if (
                delivery_status == 'sending'
                and application.updated_at >= stale_before
            ):
                skipped_in_progress += 1
                continue

            setattr(application, config.delivery_status_field, 'sending')
            setattr(application, config.batch_key_field, batch_key)
            setattr(application, config.error_field, '')
            application.updated_at = timezone.now()
            claimed.append(application)

        if claimed:
            VacancyApplication.objects.bulk_update(
                claimed,
                (
                    config.delivery_status_field,
                    config.batch_key_field,
                    config.error_field,
                    'updated_at',
                ),
            )

    return (
        claimed,
        skipped_wrong_status,
        skipped_already_sent,
        skipped_in_progress,
    )


def _mark_failed(applications, batch_key, error, config):
    VacancyApplication.objects.filter(
        pk__in=[application.pk for application in applications],
        **{
            config.batch_key_field: batch_key,
            config.delivery_status_field: 'sending',
        },
    ).update(
        **{
            config.delivery_status_field: 'failed',
            config.error_field: str(error)[:4000],
            'updated_at': timezone.now(),
        }
    )


def _mark_sent(applications, batch_key, message_ids, sent_by, config):
    sent_at = timezone.now()
    with transaction.atomic():
        locked = {
            application.pk: application
            for application in VacancyApplication.objects.select_for_update().filter(
                pk__in=[application.pk for application in applications],
                **{
                    config.batch_key_field: batch_key,
                    config.delivery_status_field: 'sending',
                },
            )
        }
        updated = []
        for application, message_id in zip(applications, message_ids):
            locked_application = locked.get(application.pk)
            if locked_application is None:
                continue
            setattr(locked_application, config.delivery_status_field, 'sent')
            setattr(locked_application, config.message_id_field, str(message_id))
            setattr(locked_application, config.sent_at_field, sent_at)
            setattr(locked_application, config.sent_by_field, sent_by)
            setattr(locked_application, config.error_field, '')
            locked_application.updated_at = sent_at
            updated.append(locked_application)

        if updated:
            VacancyApplication.objects.bulk_update(
                updated,
                (
                    config.delivery_status_field,
                    config.message_id_field,
                    config.sent_at_field,
                    config.sent_by_field,
                    config.error_field,
                    'updated_at',
                ),
            )
    return len(updated)


def send_application_email_batch(queryset, sent_by, config):
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
        ) = _claim_applications(application_id_chunk, batch_key, config)
        totals['skipped_wrong_status'] += skipped_wrong_status
        totals['skipped_already_sent'] += skipped_already_sent
        totals['skipped_in_progress'] += skipped_in_progress
        if not applications:
            continue

        message_versions = [
            {
                'to': [
                    {
                        'email': application.email,
                        'name': application.full_name,
                    }
                ],
                'params': config.params_builder(application),
            }
            for application in applications
        ]
        try:
            message_ids = config.send_batch(
                message_versions=message_versions,
                template_id=config.template_id,
                idempotency_key=batch_key,
            )
        except Exception as error:
            _mark_failed(applications, batch_key, error, config)
            totals['failed'] += len(applications)
            continue

        totals['sent'] += _mark_sent(
            applications,
            batch_key,
            message_ids,
            sent_by,
            config,
        )

    return ApplicationEmailBatchResult(**totals)
