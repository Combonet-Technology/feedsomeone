import requests
from django.core.exceptions import ValidationError


def clean_email(email: str) -> bool:
    domain = 'https://' + email.split('@')[-1]
    ext = email.split('.')[-1]
    if ext not in ['org', 'com', 'ng', 'gov', 'ca', 'us']:
        raise ValidationError('Email recipient not supported, use an official, gmail or outlook account')
    try:
        resp = requests.get(domain)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError as errc:
        print("Error Connecting:", errc)
        raise ValidationError('Email has invalid domain')
    except Exception as err:
        print("OOps: Something Else", err)
    return True
