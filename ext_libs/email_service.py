import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class EmailProviderError(Exception):
    pass


def _brevo_headers():
    if not settings.BREVO_API_KEY:
        raise EmailProviderError("BREVO_API_KEY is not configured")
    return {
        "accept": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json",
    }


def _recipients(destination):
    if isinstance(destination, (list, tuple, set)):
        recipients = [email for email in destination if email]
        if not recipients:
            raise EmailProviderError("At least one email recipient is required")
        return [{"email": email} for email in recipients]
    if not destination:
        raise EmailProviderError("At least one email recipient is required")
    return [{"email": destination}]


def send_email(destination, subject, content, source=None, plain=False):
    sender_email = source or settings.BREVO_SENDER_EMAIL
    if not sender_email:
        raise EmailProviderError("BREVO_SENDER_EMAIL is not configured")

    payload = {
        "sender": {
            "name": settings.BREVO_SENDER_NAME,
            "email": sender_email,
        },
        "to": _recipients(destination),
        "subject": subject,
    }
    if settings.BREVO_REPLY_TO_EMAIL:
        payload["replyTo"] = {"email": settings.BREVO_REPLY_TO_EMAIL}
    if plain:
        payload["textContent"] = content
    else:
        payload["htmlContent"] = content

    response = requests.post(
        f"{settings.BREVO_API_BASE_URL}/smtp/email",
        headers=_brevo_headers(),
        json=payload,
        timeout=settings.BREVO_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        logger.error("Brevo email send failed: %s %s", response.status_code, response.text)
        raise EmailProviderError(f"Brevo email send failed with status {response.status_code}")
    return True


def upsert_newsletter_contact(email, attributes=None):
    payload = {
        "email": email,
        "updateEnabled": True,
        "attributes": attributes or {},
    }
    if settings.BREVO_NEWSLETTER_LIST_ID:
        payload["listIds"] = [settings.BREVO_NEWSLETTER_LIST_ID]

    response = requests.post(
        f"{settings.BREVO_API_BASE_URL}/contacts",
        headers=_brevo_headers(),
        json=payload,
        timeout=settings.BREVO_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        logger.error("Brevo contact sync failed: %s %s", response.status_code, response.text)
        raise EmailProviderError(f"Brevo contact sync failed with status {response.status_code}")
    return True
