"""Fast, isolated settings for automated tests."""

import os

from .base import *  # noqa: F401,F403

SECRET_KEY = 'test-only-secret-key'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', 'example.com', 'google.com', 'mail.com']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('TEST_DATABASE_NAME', ':memory:'),
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Legacy project migrations contain PostgreSQL-specific operations. Tests build
# the local app tables directly from the current models while retaining Django
# and third-party migrations.
MIGRATION_MODULES = {
    'blog': None,
    'contact': None,
    'errors': None,
    'events': None,
    'mainsite': None,
    'user': None,
}
