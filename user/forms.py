# from captcha.fields import ReCaptchaField
# from captcha.widgets import ReCaptchaV2Checkbox
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.forms import FileInput, ImageField, Textarea

from user.models import Volunteer


class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'username', 'email']

    # def clean_email(self):
    #     email = self.cleaned_data.get('email')
    #     clean_email(email)
    #     return email


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']

    # def clean_email(self):
    #     email = self.cleaned_data.get('email')
    #     clean_email(email)
    #     return email


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
