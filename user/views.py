from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.generic import DetailView, ListView

from ext_libs.sendgrid.sengrid import send_email

from .forms import (UserRegistrationForm, VolunteerRegistrationForm,
                    VolunteerUpdateForm)
from .models import UserProfile
from .token import account_activation_token


@login_required()
def profile(request):
    current_user_profile = UserProfile.objects.filter(
        id=request.user.id).first()
    if request.method == 'POST':
        user_update_form = VolunteerUpdateForm(
            request.POST, request.FILES, instance=request.user)
        if user_update_form.is_valid():  # and profile_update_form.is_valid():
            user_update_form.save()
            messages.success(
                request, f'Account for {request.user} updated Successfully!')
            return redirect('profile')
    else:
        user_update_form = VolunteerUpdateForm(instance=request.user)
    context = {
        'user_update_form': user_update_form,
        'user': current_user_profile,
    }
    return render(request, 'profile.html', context)
    pass


def verify_recaptcha(g_captcha):
    # data = {
    #     'secret': settings.RECAPTCHA_PRIVATE_KEY,
    #     'response': g_captcha
    # }
    # resp = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
    # result_json = resp.json()
    return 'success'  # in result_json


# @csrf_exempt
def register(request, template='registration/register.html'):
    if request.method == 'POST':
        print(request.POST)
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
                # create volunteer
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
            return render(request, template, {'forms': user_form, 'volunteer_form': volunteer_form})
    else:
        user_form = UserRegistrationForm()
        volunteer_form = VolunteerRegistrationForm()
        return render(request, template,
                      {'forms': user_form, 'volunteer_form': volunteer_form, 'secret': settings.RECAPTCHA_PUBLIC_KEY})


def activate(request, uidb64, token):
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
        return HttpResponse('Activation link is invalid!')


class VolunteerListView(ListView):
    model = UserProfile
    context_object_name = 'volunteers'
    #    ordering = ['?']
    paginate_by = 8

    def get_queryset(self):
        return UserProfile.objects.all().order_by('date_joined')


class VolunteerDetailView(DetailView):
    model = UserProfile
    context_object_name = 'volunteer'

# todo create templates for new subscriber emails
