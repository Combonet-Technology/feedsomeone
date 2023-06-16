import requests
from django.conf import settings

from utils.extras import get_current_branch


def send_slack_message(message):
    payload = {
        'text': f'Test Summary for local stage: {settings.STAGE} on branch {get_current_branch()}',
        'blocks': [
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': message
                }
            }
        ]
    }
    try:
        response = requests.post(settings.SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print('Message sent successfully!')

    except requests.exceptions.RequestException as e:
        print(f'Failed to send message to Slack: {str(e)}')
