from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from user.models import UserProfile


class UserProfileRegistration(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)

    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name', 'username', 'email', 'password1', 'password2']


class UserProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = UserProfile
        fields = ['first_name',
                  'last_name',
                  'username',
                  'email',
                  'image',
                  'phone_number',
                  'facebook',
                  'instagram',
                  'twitter',
                  'short_bio',
                  'reason_joined',
                  'state',
                  'country']


