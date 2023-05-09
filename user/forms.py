# from captcha.fields import ReCaptchaField
# from captcha.widgets import ReCaptchaV2Checkbox
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from utils.email import clean_email


class UserProfileRegistration(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        clean_email(email)
        return email


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
