import logging

from django.conf import settings
from django.utils import timezone

from ext_libs.email_service import (send_template_email,
                                    upsert_newsletter_contact)
from ext_libs.slack.api import post_slack_webhook

from .models import VacancyApplication

logger = logging.getLogger(__name__)


def _site_link(site_url, path):
    return f"{site_url.rstrip('/')}/{path.lstrip('/')}"


def _slack_text(value):
    return str(value or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _acknowledgement_params(application):
    first_name = application.full_name.strip().split(' ', 1)[0]
    public_site_url = settings.OEF_PUBLIC_SITE_URL
    return {
        'first_name': first_name,
        'role_title': application.vacancy.title,
        'response_window': settings.VACANCY_APPLICATION_RESPONSE_WINDOW,
        'home_url': _site_link(public_site_url, '/'),
        'about_url': _site_link(public_site_url, '/about/'),
        'news_url': _site_link(public_site_url, '/article/all/'),
        'careers_url': _site_link(public_site_url, '/opportunities/'),
        'instagram_url': 'https://www.instagram.com/feedsomeone_',
        'linkedin_url': 'https://www.linkedin.com/company/feed-someone/',
        'x_url': 'https://x.com/feedsomeone_',
    }


def _cv_url(application, site_url):
    url = application.cv.url
    if url.startswith(('http://', 'https://')):
        return url
    return _site_link(site_url, url)


def _slack_payload(application, admin_url, site_url):
    phone = _slack_text(application.phone) or 'Not provided'
    cover_letter = _slack_text(application.cover_letter)
    if len(cover_letter) > 2400:
        cover_letter = f'{cover_letter[:2397]}...'
    return {
        'text': (
            f'New application for {application.vacancy.title} '
            f'from {application.full_name}'
        ),
        'blocks': [
            {
                'type': 'header',
                'text': {
                    'type': 'plain_text',
                    'text': 'New OEF vacancy application',
                },
            },
            {
                'type': 'section',
                'fields': [
                    {
                        'type': 'mrkdwn',
                        'text': f'*Role*\n{_slack_text(application.vacancy.title)}',
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f'*Applicant*\n{_slack_text(application.full_name)}',
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f'*Email*\n{_slack_text(application.email)}',
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f'*Phone*\n{phone}',
                    },
                    {
                        'type': 'mrkdwn',
                        'text': (
                            '*Received*\n'
                            f"{timezone.localtime(application.created_at).strftime('%d %b %Y, %H:%M')}"
                        ),
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f'*Status*\n{_slack_text(application.get_status_display())}',
                    },
                ],
            },
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f'*Why they want to join*\n{cover_letter}',
                },
            },
            {
                'type': 'actions',
                'elements': [
                    {
                        'type': 'button',
                        'text': {
                            'type': 'plain_text',
                            'text': 'Download CV',
                        },
                        'url': _cv_url(application, site_url),
                    },
                    {
                        'type': 'button',
                        'text': {
                            'type': 'plain_text',
                            'text': 'Review application',
                        },
                        'url': admin_url,
                        'style': 'primary',
                    },
                ],
            },
        ],
    }


def notify_new_application(application, site_url, admin_url):
    errors = []
    updates = {}

    if application.newsletter_opt_in and application.newsletter_subscribed_at is None:
        try:
            upsert_newsletter_contact(
                application.email,
                attributes={'SOURCE': 'Vacancy application'},
            )
        except Exception as exc:
            logger.exception(
                'Vacancy newsletter subscription failed for application %s',
                application.pk,
            )
            errors.append(f'Newsletter: {exc}')
        else:
            updates['newsletter_subscribed_at'] = timezone.now()

    if application.acknowledgement_sent_at is None:
        try:
            send_template_email(
                destination=application.email,
                template_id=settings.BREVO_VACANCY_ACK_TEMPLATE_ID,
                params=_acknowledgement_params(application),
            )
        except Exception as exc:
            logger.exception(
                'Vacancy acknowledgement email failed for application %s',
                application.pk,
            )
            errors.append(f'Applicant email: {exc}')
        else:
            updates['acknowledgement_sent_at'] = timezone.now()

    if application.slack_notified_at is None:
        try:
            post_slack_webhook(
                _slack_payload(application, admin_url, site_url),
                webhook_url=settings.SLACK_VACANCIES_WEBHOOK_URL,
            )
        except Exception as exc:
            logger.exception(
                'Vacancy Slack notification failed for application %s',
                application.pk,
            )
            errors.append(f'Slack: {exc}')
        else:
            updates['slack_notified_at'] = timezone.now()

    updates['notification_error'] = '\n'.join(errors)[:2000]
    VacancyApplication.objects.filter(pk=application.pk).update(**updates)
    for field, value in updates.items():
        setattr(application, field, value)

    return not errors
