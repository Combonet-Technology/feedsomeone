import copy
import logging

import requests
from django.conf import settings

from utils.enums import ColorCodes

# Configure the logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SlackWebhookError(Exception):
    pass


def post_slack_webhook(payload, webhook_url=None):
    url = webhook_url or settings.SLACK_WEBHOOK_URL
    if not url:
        raise SlackWebhookError('Slack webhook URL is not configured')

    response = requests.post(
        url,
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=settings.SLACK_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return True


def build_slack_test_result(results):
    from utils.extras import get_current_branch

    branch = get_current_branch()
    header = f'Test Summary for local stage: {settings.STAGE} on branch {branch}'
    block = list()
    starter = {
        'fields': [{
            'value': None
        }]
    }
    for idx, result in enumerate(results):
        if len(result) > 0:
            starter_copy = copy.deepcopy(starter)
            if idx == 0:
                starter_copy['title'] = ColorCodes.SUCCESS.name
                starter_copy['color'] = ColorCodes.SUCCESS.value
                starter_copy['fields'][0]['value'] = f'{len(result)} tests'
            elif idx == 1:
                starter_copy['title'] = ColorCodes.FAILURE.name
                starter_copy['color'] = ColorCodes.FAILURE.value
                starter_copy['fields'][0]['value'] = f'{len(result)} tests'
            elif idx == 2:
                starter_copy['title'] = ColorCodes.ERROR.name
                starter_copy['color'] = ColorCodes.ERROR.value
                starter_copy['fields'][0]['value'] = f'{len(result)} tests'
            block.append(starter_copy)
    payload = {
        'text': f'*{header}*',
        'attachments': block
    }

    return payload


def send_slack_message(message):
    payload = build_slack_test_result(message)
    try:
        post_slack_webhook(payload)
        logger.info('Message sent successfully!')
    except requests.exceptions.RequestException:
        logger.error('Failed to send message to Slack due to connection failure')
    except Exception as e:
        logger.exception(f'Unexpected error occurred: {str(e)}')
