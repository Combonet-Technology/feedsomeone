from decouple import config
from sendgrid import Mail, SendGridAPIClient


def send_html_email(source, destination, subject, content, plain=False):
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
    try:
        sg = SendGridAPIClient(config('SENDGRID_API_KEY'))
        response = sg.send(message)
    except Exception as e:
        print(e)
        return False
    else:
        print(response.status_code)
        print(response.body)
        print(response.headers)
        return True
