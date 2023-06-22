from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites import shortcuts
from django.forms import FileInput, ImageField, Textarea
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _

from ext_libs.sendgrid import sengrid
from user.models import Volunteer
from utils.forms import clean_email


class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'username', 'email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        clean_email(email)
        return email


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        clean_email(email)
        return email


class VolunteerRegistrationForm(forms.ModelForm):
    class Meta:
        model = Volunteer
        fields = ['phone_number', 'state_of_residence']


class VolunteerUpdateForm(forms.ModelForm):
    image = ImageField(widget=FileInput)
    short_bio = forms.CharField(required=False, widget=Textarea)

    class Meta:
        model = Volunteer
        fields = ['image', 'phone_number', 'profession', 'ethnicity', 'religion', 'state_of_residence', 'short_bio', ]


class CustomPasswordResetForm(PasswordResetForm):

    def send_mail(self, context, to_email, *args, **kwargs):
        email_template_name = 'registration/password_reset_email.html'
        body = loader.render_to_string(email_template_name, context)
        sengrid.send_email(destination=to_email, subject=f"Password reset on {context['site_name']}", content=body)

    def save(self, use_https=False, request=None, *args, **kwargs):
        email = self.cleaned_data["email"]
        current_site = shortcuts.get_current_site(request)
        site_name = current_site.name
        domain = current_site.domain
        email_field_name = get_user_model().get_email_field_name()
        for user in self.get_users(email):
            user_email = getattr(user, email_field_name)
            context = {
                'email': user_email,
                'domain': domain,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'user': user,
                'token': default_token_generator.make_token(user),
                'protocol': 'https' if use_https else 'http',
            }
            self.send_mail(context, user_email)


class UsernameForm(forms.Form):
    username = forms.CharField(max_length=255, label='create your username',
                               help_text=_('Enter a username for your account.'))
