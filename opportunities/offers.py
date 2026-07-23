import base64
import mimetypes
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.utils.html import strip_tags

from ext_libs.email_service import send_email

from .models import VacancyApplication, VolunteerOffer


class OfferAlreadySent(Exception):
    pass


class OfferDeliveryInProgress(Exception):
    pass


@dataclass(frozen=True)
class OfferDocumentContext:
    offer: VolunteerOffer
    recipient_first_name: str
    formatted_letter_date: str
    formatted_start_date: str
    formatted_acceptance_deadline: str
    sender_name: str
    sender_title: str
    logo_data_uri: str
    logo_url: str


def _first_name(full_name):
    return full_name.strip().split(' ', 1)[0]


def _format_date(value):
    return date_format(value, 'j F Y') if value else ''


def _logo_data_uri():
    logo_path = finders.find('img/logo/oef-logo.svg')
    if not logo_path:
        return ''
    content = Path(logo_path).read_bytes()
    mime_type = mimetypes.guess_type(logo_path)[0] or 'image/svg+xml'
    encoded = base64.b64encode(content).decode('ascii')
    return 'data:' + mime_type + ';base64,' + encoded


def _logo_url():
    return f"{settings.OEF_PUBLIC_SITE_URL.rstrip('/')}{static('img/logo/oef-logo-email.png')}"


def _document_context(offer):
    return OfferDocumentContext(
        offer=offer,
        recipient_first_name=_first_name(offer.recipient_name),
        formatted_letter_date=_format_date(offer.letter_date),
        formatted_start_date=_format_date(offer.start_date),
        formatted_acceptance_deadline=_format_date(offer.acceptance_deadline),
        sender_name=settings.OEF_VOLUNTEER_OFFER_SIGNATORY_NAME,
        sender_title=settings.OEF_VOLUNTEER_OFFER_SIGNATORY_TITLE,
        logo_data_uri=_logo_data_uri(),
        logo_url=_logo_url(),
    )


def render_offer_pdf(offer):
    from weasyprint import HTML

    html = render_to_string(
        'opportunities/volunteer_offer_letter.html',
        {'document': _document_context(offer)},
    )
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


def _safe_pdf_name(recipient_name):
    safe_name = re.sub(r'[^A-Za-z0-9 ._-]+', '', recipient_name).strip()
    return f'OEF Volunteer Engagement Letter - {safe_name or "Volunteer"}.pdf'


def _offer_values(application, form_data):
    return {
        'recipient_name': application.full_name,
        'recipient_email': application.email,
        'role_title': application.vacancy.title,
        'letter_date': timezone.localdate(),
        'start_date': form_data['start_date'],
        'initial_period': form_data['initial_period'].strip(),
        'weekly_commitment': form_data['weekly_commitment'].strip(),
        'work_arrangement': form_data['work_arrangement'].strip(),
        'reporting_contact': form_data['reporting_contact'].strip(),
        'role_contribution': form_data['role_contribution'].strip(),
        'acceptance_deadline': form_data.get('acceptance_deadline'),
    }


def _mark_delivery_failed(offer_id, error):
    VolunteerOffer.objects.filter(pk=offer_id).update(
        delivery_status='failed',
        delivery_error=str(error)[:4000],
        updated_at=timezone.now(),
    )


def send_volunteer_offer(application, form_data, sent_by):
    with transaction.atomic():
        application = (
            VacancyApplication.objects.select_for_update()
            .select_related('vacancy')
            .get(pk=application.pk)
        )
        offer = (
            VolunteerOffer.objects.select_for_update()
            .filter(application=application)
            .first()
        )
        if offer and offer.sent_at:
            raise OfferAlreadySent('A volunteer offer has already been sent to this applicant.')
        recently_started = (
            offer
            and offer.delivery_status == 'sending'
            and offer.updated_at >= timezone.now() - timedelta(minutes=15)
        )
        if recently_started:
            raise OfferDeliveryInProgress('This offer is already being processed.')

        values = _offer_values(application, form_data)
        if offer is None:
            offer = VolunteerOffer(application=application, **values)
        else:
            for field, value in values.items():
                setattr(offer, field, value)
        offer.delivery_status = 'sending'
        offer.delivery_error = ''
        offer.save()

    try:
        pdf_content = render_offer_pdf(offer)
        if offer.letter_pdf:
            offer.letter_pdf.delete(save=False)
        offer.letter_pdf.save(
            _safe_pdf_name(offer.recipient_name),
            ContentFile(pdf_content),
            save=True,
        )

        document = _document_context(offer)
        email_html = render_to_string(
            'opportunities/email/volunteer_offer.html',
            {'document': document},
        )
        message_id = send_email(
            destination=offer.recipient_email,
            subject=(
                'Your OEF Volunteer Engagement Offer - '
                f'{offer.role_title.removeprefix("Volunteer ")}'
            ),
            content=email_html,
            text_content=strip_tags(email_html),
            attachments=(
                {
                    'name': _safe_pdf_name(offer.recipient_name),
                    'content': pdf_content,
                },
            ),
            message_headers={'Idempotency-Key': str(offer.delivery_key)},
        )
    except Exception as error:
        _mark_delivery_failed(offer.pk, error)
        raise

    sent_at = timezone.now()
    with transaction.atomic():
        VolunteerOffer.objects.filter(pk=offer.pk).update(
            delivery_status='sent',
            delivery_error='',
            brevo_message_id='' if message_id is True else str(message_id),
            sent_at=sent_at,
            sent_by=sent_by,
            updated_at=sent_at,
        )
        VacancyApplication.objects.filter(pk=application.pk).update(
            status='offered',
            updated_at=sent_at,
        )

    offer.refresh_from_db()
    return offer
