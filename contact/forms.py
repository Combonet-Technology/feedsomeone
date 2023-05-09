import requests
from django import forms
from django.contrib.auth import get_user_model
from django.forms import ModelForm

from contact.models import Contact
from user.models import Lead
from utils.email import clean_email


class ContactForm(ModelForm):
    class Meta:
        model = Contact
        fields = ['firstname', 'lastname', 'email', 'subject', 'message']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        clean_email(email)
        return email


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
