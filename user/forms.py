# from captcha.fields import ReCaptchaField
# from captcha.widgets import ReCaptchaV2Checkbox
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from user.models import Volunteer
from utils.email import clean_email


class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'username', 'email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        clean_email(email)
        return email


class VolunteerRegistrationForm(forms.ModelForm):
    class Meta:
        model = Volunteer
        fields = ['state', 'country']


class VolunteerUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = Volunteer
        fields = ['state', 'short_bio', 'image', 'phone_number']
