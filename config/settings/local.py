"""
Django settings for config local server.

Generated by 'django-admin startproject' using Django 3.1.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

from dotenv import load_dotenv

load_dotenv()

from .base import *

ALLOWED_HOSTS = ['*']
# debug toolbar settings
INSTALLED_APPS.insert(-1, 'debug_toolbar')
MIDDLEWARE.insert(5, 'debug_toolbar.middleware.DebugToolbarMiddleware')

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_COLLAPSED': True,
}
DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB_NAME'),
        'USER': os.environ.get('POSTGRES_DB_USER'),
        'PASSWORD': os.environ.get('POSTGRES_DB_PASS'),
        'HOST': os.environ.get('POSTGRES_HOST'),
        'PORT': os.environ.get('POSTGRES_PORT')
    }
}
# for custom error handler
TEMPLATE_DEBUG = DEBUG

# for debug toolbar
INTERNAL_IPS = (
    '127.0.0.1',
)

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
