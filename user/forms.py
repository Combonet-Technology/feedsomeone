# from captcha.fields import ReCaptchaField
# from captcha.widgets import ReCaptchaV2Checkbox
import requests
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from user.models import Lead


class UserProfileRegistration(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'username', 'email', 'password1', 'password2']


class UserProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = get_user_model()
        fields = ['first_name',
                  'last_name',
                  'username',
                  'email',
                  'image',
                  'phone_number']


class NewsletterForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = Lead
        fields = ['email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if get_user_model().objects.get(email):
            raise Exception('Email already registered to another user')
        resp = requests.get(email.split('@')[-1])
        if resp.status_code != 200:
            raise Exception('Email invalid')
