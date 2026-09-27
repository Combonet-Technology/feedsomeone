"""Isolated PostgreSQL tests using the project's configured database server."""

import os

from .base import *  # noqa: F401, F403

SECRET_KEY = 'test-only-secret-key'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1', 'example.com', 'google.com', 'mail.com']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['POSTGRES_DB_NAME'],
        'USER': os.environ['POSTGRES_DB_USER'],
        'PASSWORD': os.environ['POSTGRES_DB_PASS'],
        'HOST': os.environ['POSTGRES_HOST'],
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        # Django creates test_<NAME>; never point TEST.NAME at application data.
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
TEST_RUNNER = 'django.test.runner.DiscoverRunner'
OEF_CLOUDINARY_ENVIRONMENT = 'test'

# Custom API clients do not use Django's in-memory email backend.
BREVO_API_KEY = ''
SLACK_WEBHOOK_URL = ''
SLACK_VACANCIES_WEBHOOK_URL = ''
OEF_SLACK_INVITE_URL = ''

# Run real migrations, including PostgreSQL-specific schema operations.
