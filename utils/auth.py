from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.utils.http import urlsafe_base64_decode


def get_user(uidb64):
    User = get_user_model()
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, ValidationError):
        user = None
    return user


def set_password_and_login(user, request, form, authenticated=None):
    """
    Perform the set password action for the given user and form.
    """
    if request.method == 'POST':
        filled_form = form(user, request.POST)
        if filled_form.is_valid():
            filled_form.save()
            authenticated_user = authenticate(request, username=user.email,
                                              password=filled_form.cleaned_data['new_password1'])
            if authenticated_user is not None:
                login(request, authenticated_user, backend='django.contrib.auth.backends.ModelBackend')
            return None, True
    form = form(user)
    return form, False


def check_validity_token(request, user, token):
    INTERNAL_RESET_SESSION_TOKEN = '_password_reset_token'
    reset_url_token = 'set-password'
    if token == reset_url_token:
        session_token = request.session.get(INTERNAL_RESET_SESSION_TOKEN)
        if default_token_generator.check_token(user, session_token):
            # valid token
            return True
    else:
        if default_token_generator.check_token(user, token):
            request.session[INTERNAL_RESET_SESSION_TOKEN] = token
            redirect_url = request.path.replace(token, reset_url_token)
            return HttpResponseRedirect(redirect_url)
    return False
