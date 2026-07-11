from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import ModelForm

from contact.models import Contact
from user.models import Lead
from utils.forms import clean_email


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
        clean_email(email)
        if get_user_model().objects.filter(email=email).exists():
            raise ValidationError('Email already registered to another user')
        if Lead.objects.filter(email=email).exists():
            raise ValidationError('Email already subscribed')
        return email
