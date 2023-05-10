"""
Django settings for config project.

Generated by 'django-admin startproject' using Django 3.1.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

import os
from pathlib import Path

from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Application definition
SECRET_KEY = config('SECRET_KEY')
INSTALLED_APPS = [
    'baton',
    # 'djangocms_admin_style',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'mainsite.apps.MainsiteConfig',
    'blog.apps.BlogConfig',
    'user.apps.UserConfig',
    'events.apps.EventsConfig',
    'contact.apps.ContactConfig',
    'django.contrib.postgres',
    'crispy_forms',
    'imagefit',
    'django_summernote',
    'import_export',
    'django.contrib.humanize',
    'errors.apps.ErrorsConfig',
    'captcha',
    'baton.autodiscover',
    # 'cms',
    'menus',
    'treebeard',
    'sekizai',
    'taggit',
]

MIDDLEWARE = [
    # 'cms.middleware.utils.ApphookReloadMiddleware'
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'cms.middleware.user.CurrentUserMiddleware',
    # 'cms.middleware.page.CurrentPageMiddleware',
    # 'cms.middleware.toolbar.ToolbarMiddleware',
    # 'cms.middleware.language.LanguageCookieMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'sekizai.context_processors.sekizai',
                # 'cms.context_processors.cms_settings',
                'django.template.context_processors.i18n',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

LANGUAGES = [
    ('en-us', 'English'),
    ('de', 'German'),
    ('fr', 'French'),
]

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

SITE_ID = 1

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'assets'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

CRISPY_TEMPLATE_PACK = 'bootstrap4'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

LOGIN_REDIRECT_URL = 'profile'
LOGIN_URL = 'login'

IMAGEFIT_ROOT = BASE_DIR

# summernote config
X_FRAME_OPTIONS = 'SAMEORIGIN'
SUMMERNOTE_THEME = 'bs4'
# SUMMERNOTE_CONFIG['disable_attachment'] = True

AUTH_USER_MODEL = 'user.UserProfile'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
RECAPTCHA_PUBLIC_KEY = config('RECAPTCHA_PUBLIC_KEY_v3')
RECAPTCHA_PRIVATE_KEY = config('RECAPTCHA_PRIVATE_KEY_v3')

BATON = {
    'SITE_HEADER': 'Oluwafemi Ebenezer Foundation',
    'SITE_TITLE': 'OEF BACKEND',
    'INDEX_TITLE': 'OEF administration',
    'SUPPORT_HREF': 'mailto:info@oluwafemiebenezerfoundation.org',
    'COPYRIGHT': 'copyright © 2020 <a href="https://www.otto.to.it">Otto srl</a>',  # noqa
    'POWERED_BY': '<a href="https://www.otto.to.it">Otto srl</a>',
    'CONFIRM_UNSAVED_CHANGES': True,
    'SHOW_MULTIPART_UPLOADING': True,
    'ENABLE_IMAGES_PREVIEW': True,
    'CHANGELIST_FILTERS_IN_MODAL': True,
    'CHANGELIST_FILTERS_ALWAYS_OPEN': False,
    'CHANGELIST_FILTERS_FORM': True,
    'MENU_ALWAYS_COLLAPSED': False,
    'MENU_TITLE': 'Menu',
    'MESSAGES_TOASTS': False,
    'GRAVATAR_DEFAULT_IMG': 'retro',
    'LOGIN_SPLASH': '/static/core/img/login-splash.png',
    'SEARCH_FIELD': {
        'label': 'Search contents...',
        'url': '/search/',
    },
    'MENU': (
        {'type': 'title', 'label': 'main', 'apps': ('auth',)},
        {
            'type': 'app',
            'name': 'auth',
            'label': 'Authentication',
            'icon': 'fa fa-lock',
            'models': (
                {
                    'name': 'user',
                    'label': 'Users'
                },
                {
                    'name': 'group',
                    'label': 'Groups'
                },
            )
        },
        {'type': 'title', 'label': 'Contents', 'apps': ('flatpages',)},
        {'type': 'model', 'label': 'Pages', 'name': 'flatpage', 'app': 'flatpages'},
        {
            'type': 'free', 'label': 'Custom Link', 'url': 'http://www.google.it',
            'perms': ('flatpages.add_flatpage', 'auth.change_user')
        },
        {
            'type': 'free', 'label': 'My parent voice', 'default_open': True, 'children': [
            {'type': 'model', 'label': 'A Model', 'name': 'mymodelname', 'app': 'myapp'},
            {'type': 'free', 'label': 'Another custom link', 'url': 'http://www.google.it'},
        ]
        },
    ),
    # 'ANALYTICS': {
    #     'CREDENTIALS': os.path.join(BASE_DIR, 'credentials.json'),
    #     'VIEW_ID': '12345678',
    # }
}

CMS_TEMPLATES = [
    ('index.html', 'Home page template'),
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend'
]


IMAGEFIT_PRESETS = {
    'thumbnail': {'width': 64, 'height': 64, 'crop': True},
    'my_preset1': {'width': 300, 'height': 220},
    'my_preset2': {'width': 100},
}

EMAIL_HOST_USER = config('EMAIL_HOST_USER')
GMAIL_EMAIL = config('GMAIL_EMAIL')
OUTLOOK_EMAIL = config('OUTLOOK_EMAIL')
