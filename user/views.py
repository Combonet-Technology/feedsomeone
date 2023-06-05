import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.views import PasswordResetView
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from social_core.exceptions import AuthCanceled
from social_django.utils import psa
from social_django.views import NAMESPACE

from ext_libs.python_social.social_auth_backends import do_complete
from ext_libs.sendgrid.sengrid import send_email
from utils.auth import check_validity_token, get_user, set_password_and_login
from utils.decorators import ajax_required
from utils.views import custom_paginator, get_actual_template

from .forms import (CustomPasswordResetForm, UsernameForm,
                    UserRegistrationForm, VolunteerRegistrationForm,
                    VolunteerUpdateForm)
from .models import UserProfile, Volunteer
from .token import account_activation_token


@login_required()
def profile(request):
    current_user_profile = request.user.volunteer
    if request.method == 'POST':
        update_form_volunteer = VolunteerUpdateForm(
            request.POST, request.FILES, instance=current_user_profile)
        if update_form_volunteer.is_valid():
            update_form_volunteer.save()
            messages.success(
                request, f'Account for {request.user} updated Successfully!')
            return redirect('profile')
    else:
        initial_data = {field_name: getattr(current_user_profile, field_name) for field_name in
                        VolunteerUpdateForm.Meta.fields}
        update_form_volunteer = VolunteerUpdateForm(instance=request.user, initial=initial_data)
    context = {
        'user_update_form': update_form_volunteer,
        'user': current_user_profile,
        'small_fields': ['state_of_residence', 'ethnicity', 'religion']
    }
    return render(request, 'profile.html', context)


def verify_recaptcha(g_captcha):
    data = {
        'secret': settings.RECAPTCHA_PRIVATE_KEY,
        'response': g_captcha
    }
    resp = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
    result_json = resp.json()
    return 'success' in result_json


def register(request, template='registration/register.html'):
    if request.method == 'POST':
        g_captcha = request.POST.get('g-recaptcha-response')
        user_form = UserRegistrationForm(request.POST)
        volunteer_form = VolunteerRegistrationForm(request.POST)

        # verify recaptcha
        if not verify_recaptcha(g_captcha):
            return render(request, 'robot_response.html', {'is_robot': True})

        if user_form.is_valid() and volunteer_form.is_valid():
            with transaction.atomic():
                user = user_form.save(commit=False)
                current_site = get_current_site(request)
                send_email(settings.EMAIL_NO_REPLY,
                           user_form.cleaned_data.get('email'),
                           'Activation link has been sent to your email id',
                           render_to_string('acc_activation_email.html', {
                               'username': user.username,
                               'domain': current_site.domain,
                               'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                               'token': account_activation_token.make_token(user),
                           }))
                username = user_form.cleaned_data.get('username')
                volunteer = volunteer_form.save(commit=False)
                volunteer.user = user
                user.save()
                volunteer.save()

            data = {
                'msg': 'Please check your inbox or spam folder for next steps on how to complete the registration',
                'subject': f'Account creation for {username} started!',
                'title': 'Feedsomeone - registration next step',
            }
            return render(request, 'thank-you.html', data)
        else:
            messages.error(request, 'INVALID USER INPUTS')
    else:
        user_form = UserRegistrationForm()
        volunteer_form = VolunteerRegistrationForm()
    return render(request, template,
                  {'forms': user_form, 'volunteer_form': volunteer_form, 'secret': settings.RECAPTCHA_PUBLIC_KEY})


def activate(uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        return redirect('login')
    else:
        return HttpResponse('Activation link is invalid or expired!')


class VolunteerListView(ListView):
    model = Volunteer
    context_object_name = 'objects'
    template_name = 'user/userprofile_list.html'
    paginate_by = 8

    def get_template_names(self):
        template_names = super().get_template_names()
        return get_actual_template(self, 'user/userprofile_ajax.html') + template_names

    def paginate_queryset(self, queryset, page_size):
        return custom_paginator(self.request, page_size, queryset)


class VolunteerDetailView(DetailView):
    model = UserProfile
    context_object_name = 'volunteer'


@never_cache
@csrf_exempt
@psa(f"{NAMESPACE}:complete")
def social_auth_complete(request, backend, *args, **kwargs):
    response = do_complete(request.backend, user=request.user, *args, **kwargs)
    try:
        pass
    except AuthCanceled:
        return redirect('login')

    except Exception as e:
        print(str(e))
        return redirect('login')
    else:
        if response.status_code == 302 and request.user.is_authenticated:
            user = request.user
            if hasattr(user, 'volunteer'):
                if user.has_usable_password():
                    return redirect('profile')
            return redirect(set_password_view)


class InitiatePasswordReset(PasswordResetView):
    form_class = CustomPasswordResetForm


def set_password_view(request, uidb64=None, token=None):
    already_logged, motive, user = reset_from_source(request, token, uidb64)

    if user and not already_logged:
        if not check_validity_token(request, user, token):
            # return 400 page with the error
            return HttpResponse('Invalid Token, Request for another with valid credentials')
    form, done = set_password_and_login(user, request, SetPasswordForm,
                                        authenticated=already_logged)
    if done:
        return profile(request)
        # return redirect('profile')
    return render(request, 'registration/password_change_form.html',
                  context={'form': form, 'motive': motive})


def reset_from_source(request, token, uidb64):
    motive = ''
    already_logged = False
    user = None
    if uidb64 and token:
        user = get_user(uidb64=uidb64)
        motive = 'Change'
    elif request.user.is_authenticated:
        user = request.user
        motive = 'Set'
        already_logged = True
    return already_logged, motive, user


def create_username(request):
    if request.method == 'POST':
        form = UsernameForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            user = request.user
            user.username = username
            user.save()
            return redirect('profile')
    else:
        form = UsernameForm()
    return render(request, 'create_username.html', {'form': form})


@ajax_required
@require_POST
@login_required()
def check_username_availability(request):
    username = request.POST.get('username')
    is_available = not UserProfile.objects.filter(username=username).exists()
    return JsonResponse({'available': is_available})

# todo create templates for new subscriber emails
