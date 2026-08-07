from django.conf import settings

from ext_libs.email_service import (EmailProviderError,
                                    send_template_email_batch)

from .application_email_batches import (ApplicationEmailBatchConfig,
                                        ApplicationEmailBatchResult,
                                        first_name,
                                        send_application_email_batch)

ELIGIBLE_APPLICATION_STATUSES = frozenset({'reviewing', 'shortlisted'})
InterviewBatchResult = ApplicationEmailBatchResult


def _params(application):
    return {
        'first_name': first_name(application.full_name),
        'role_title': application.vacancy.title,
        'booking_url': settings.OEF_INTERVIEW_BOOKING_URL,
    }


def send_interview_invitation_batch(queryset, sent_by):
    if not settings.OEF_INTERVIEW_BOOKING_URL:
        raise EmailProviderError('OEF_INTERVIEW_BOOKING_URL is not configured')

    return send_application_email_batch(
        queryset,
        sent_by,
        ApplicationEmailBatchConfig(
            eligible_statuses=ELIGIBLE_APPLICATION_STATUSES,
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
