from django.conf import settings
from sendgrid import Cc, Mail, Personalization, SendGridAPIClient


def send_email(destination, subject, content, source=None, plain=False):
    source = source or settings.EMAIL_NO_REPLY
    is_multiple = True if isinstance(destination, list) else False
    if not plain:
        message = Mail(
            from_email=source,
            to_emails=destination,
            subject=subject,
            html_content=content,
            is_multiple=is_multiple)
    else:
        message = Mail(
            from_email=source,
            to_emails=destination,
            subject=subject,
            plain_text_content=content,
            is_multiple=is_multiple)
        personalization = Personalization()
        personalization.add_email(Cc(settings.OUTLOOK_EMAIL))
        message.add_personalization(personalization)
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        raise Exception(str(e))
    else:
        return True
