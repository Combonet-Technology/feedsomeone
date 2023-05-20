from urllib.parse import quote

from social_core.utils import (partial_pipeline_data, sanitize_redirect,
                               setting_url, user_is_active,
                               user_is_authenticated)
from social_django.views import _do_login


def do_complete(backend, user=None, redirect_name="next", *args, **kwargs):
    data = backend.strategy.request_data()

    is_authenticated = user_is_authenticated(user)
    user = user if is_authenticated else None

    partial = partial_pipeline_data(backend, user, *args, **kwargs)
    if partial:
        user = backend.continue_pipeline(partial)
        # clean partial data after usage
        backend.strategy.clean_partial_pipeline(partial.token)
    else:
        user = backend.complete(user=user, *args, **kwargs)

    # pop redirect value before the session is trashed on login(), but after
    # the pipeline so that the pipeline can change the redirect if needed
    redirect_value = backend.strategy.session_get(redirect_name, "") or data.get(
        redirect_name, ""
    )

    # check if the output value is something else than a user and just
    # return it to the client
    user_model = backend.strategy.storage.user.user_model()
    if user and not isinstance(user, user_model):
        return user

    if is_authenticated:
        if not user:
            url = setting_url(backend, redirect_value, "LOGIN_REDIRECT_URL")
        else:
            url = setting_url(
                backend,
                redirect_value,
                "NEW_ASSOCIATION_REDIRECT_URL",
                "LOGIN_REDIRECT_URL",
            )
    elif user:
        if user_is_active(user):
            # catch is_new/social_user in case login() resets the instance
            is_new = getattr(user, "is_new", False)
            social_user = user.social_user if hasattr(user, 'social_user') else None
            _do_login(backend, user, social_user)
            # store last login backend name in session
            backend.strategy.session_set("social_auth_last_login_backend", getattr(social_user, 'provider', ''))
            if is_new:
                url = setting_url(
                    backend,
                    "NEW_USER_REDIRECT_URL",
                    redirect_value,
                    "LOGIN_REDIRECT_URL",
                )
            else:
                url = setting_url(backend, redirect_value, "LOGIN_REDIRECT_URL")
        else:
            if backend.setting("INACTIVE_USER_LOGIN", False):
                social_user = user.social_user
                _do_login(backend, user, social_user)
            url = setting_url(
                backend, "INACTIVE_USER_URL", "LOGIN_ERROR_URL", "LOGIN_URL"
            )
    else:
        url = setting_url(backend, "LOGIN_ERROR_URL", "LOGIN_URL")

    if redirect_value and redirect_value != url:
        redirect_value = quote(redirect_value)
        url += ("&" if "?" in url else "?") + f"{redirect_name}={redirect_value}"

    if backend.setting("SANITIZE_REDIRECTS", True):
        allowed_hosts = backend.setting("ALLOWED_REDIRECT_HOSTS", []) + [
            backend.strategy.request_host()
        ]
        url = sanitize_redirect(allowed_hosts, url) or backend.setting(
            "LOGIN_REDIRECT_URL"
        )
    return backend.strategy.redirect(url)
