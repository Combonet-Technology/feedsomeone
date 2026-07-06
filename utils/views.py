import hashlib
import logging
import time

import requests
from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


def custom_paginator(request, page_size, queryset):
    paginator = Paginator(queryset, page_size)
    page = request.GET.get('page')
    try:
        results = paginator.page(page)
    except PageNotAnInteger:
        results = paginator.page(1)
    except EmptyPage:
        if request.is_ajax():
            return HttpResponse('')
        results = paginator.page(paginator.num_pages)
    is_paginated = len(results) > 0
    return paginator, page, results, is_paginated


def get_actual_template(view_obj, extra_template):
    if view_obj.request.is_ajax():
        return [extra_template]
    return []


def verify_recaptcha(g_captcha, expected_action='registrationForm', remote_ip=None):
    """Validate a reCAPTCHA v3 token and fail closed on malformed responses."""
    if not g_captcha or not settings.RECAPTCHA_PRIVATE_KEY:
        return False

    data = {
        'secret': settings.RECAPTCHA_PRIVATE_KEY,
        'response': g_captcha,
    }
    if remote_ip:
        data['remoteip'] = remote_ip

    try:
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data=data,
            timeout=settings.RECAPTCHA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        logger.exception('reCAPTCHA verification failed')
        return False

    try:
        score = float(result.get('score', 0))
    except (TypeError, ValueError):
        return False

    return bool(
        result.get('success') is True
        and result.get('action') == expected_action
        and score >= settings.RECAPTCHA_MIN_SCORE
    )


def generate_uidb64(user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    return uidb64


def generate_hashed_string(customer_data):
    data_string = f"{customer_data['full_name']}-{customer_data['email']}"
    hash_one = hashlib.sha256(data_string.encode()).hexdigest()
    current_timestamp = str(int(time.time()))
    hash_two = hashlib.sha256(current_timestamp.encode()).hexdigest()
    combined_hash = f"{hash_one}:{hash_two}"

    return combined_hash
