import requests
from django.core.exceptions import ValidationError


def clean_email(email):
    domain = 'https://' + email.split('@')[-1]
    ext = email.split('.')[-1]
    resp = requests.get(domain)
    if resp.status_code != 200 or ext not in ['org', 'com', 'ng', 'gov', 'ca', 'us']:
        raise ValidationError('Email recipient does not exist')
