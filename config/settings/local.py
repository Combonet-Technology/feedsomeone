"""
Django settings for config local server.

Generated by 'django-admin startproject' using Django 3.1.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

from .base import *
import os
from decouple import config


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# debug toolbar settings
INSTALLED_APPS.append('debug_toolbar')
MIDDLEWARE.insert(5, 'debug_toolbar.middleware.DebugToolbarMiddleware')

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_COLLAPSED': True,

}

# SECURITY WARNING: don't run with debug turned on in production!

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# EMAIL_HOST = 'smtp-mail.outlook.com'

AWS_ACCESS_KEY_ID = os.environ.get('FS_AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('FS_AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('FS_AWS_STORAGE_BUCKET_NAME')
# SECRET_KEY = "5f*ovu$9jd%2io#8yy0t5o6_&dt)co-_z$#=d%^#*)3)y0uu(y"
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASS')
EMAIL_PORT = 587
EMAIL_USE_TLS = True

DATABASES = {
    'default': {
        # 'ENGINE': 'django.db.backends.sqlite3',
        # 'NAME': BASE_DIR / 'db.sqlite3',
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB_NAME'),
        'USER': config('POSTGRES_DB_USER'),
        'PASSWORD': config('POSTGRES_DB_PASS'),
        'HOST': 'localhost',
        # 'PORT': ''
    }
}
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None
# AWS_QUERYSTRING_AUTH = False


# for custom error handler
TEMPLATE_DEBUG = DEBUG

# for debug toolbar
INTERNAL_IPS = (
    '127.0.0.1',
)

