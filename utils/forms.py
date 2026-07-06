from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def clean_email(email: str) -> bool:
    if not email:
        raise ValidationError('Email cannot be blank')
    validate_email(email)
    return True
