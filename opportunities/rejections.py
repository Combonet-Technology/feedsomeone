from django.conf import settings

from config.public_links import get_oef_social_links
from ext_libs.email_service import send_template_email_batch

from .application_email_batches import (ApplicationEmailBatchConfig,
                                        ApplicationEmailBatchResult,
                                        first_name,
                                        send_application_email_batch)

RejectionBatchResult = ApplicationEmailBatchResult


def _params(application):
    return {
        'first_name': first_name(application.full_name),
        'role_title': application.vacancy.title,
        'booking_url': settings.OEF_INTERVIEW_BOOKING_URL,
        **get_oef_social_links(),
    }


def send_rejection_email_batch(queryset, sent_by):
    return send_application_email_batch(
        queryset,
        sent_by,
        ApplicationEmailBatchConfig(
            eligible_statuses=frozenset({'not_selected'}),
            delivery_status_field='rejection_email_status',
            batch_key_field='rejection_email_batch_key',
            message_id_field='rejection_email_message_id',
            sent_at_field='rejection_email_sent_at',
            sent_by_field='rejection_email_sent_by',
            error_field='rejection_email_error',
            template_id=settings.BREVO_REJECTION_TEMPLATE_ID,
            params_builder=_params,
            send_batch=send_template_email_batch,
        ),
    )


def send_interview_invite_email_batch(queryset, sent_by):

    return send_application_email_batch(
        queryset,
        sent_by,
        ApplicationEmailBatchConfig(
            eligible_statuses=frozenset({'shortlisted'}),
            delivery_status_field='interview_email_status',
            batch_key_field='interview_email_batch_key',
            message_id_field='interview_email_message_id',
            sent_at_field='interview_email_sent_at',
            sent_by_field='interview_email_sent_by',
            error_field='interview_email_error',
            template_id=settings.BREVO_INTERVIEW_TEMPLATE_ID,
            params_builder=_params,
            send_batch=send_template_email_batch,
        ),
    )
