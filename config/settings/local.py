"""
Django settings for config local server.

Generated by 'django-admin startproject' using Django 3.1.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

from .base import *
from decouple import config
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# debug toolbar settings
INSTALLED_APPS.append('debug_toolbar')
MIDDLEWARE.insert(5, 'debug_toolbar.middleware.DebugToolbarMiddleware')

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_COLLAPSED': True,
}
DEBUG = True

EMAIL_HOST_USER = config('EMAIL_HOST_USER')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB_NAME'),
        'USER': config('POSTGRES_DB_USER'),
        'PASSWORD': config('POSTGRES_DB_PASS'),
        'HOST': 'localhost',
        'PORT': 5433
    }
}
# for custom error handler
TEMPLATE_DEBUG = DEBUG

# for debug toolbar
INTERNAL_IPS = (
    '127.0.0.1',
)
