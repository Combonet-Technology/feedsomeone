from django.forms import ModelForm

from contact.models import Contact
from utils.email import clean_email


class ContactForm(ModelForm):
    class Meta:
        model = Contact
        fields = ['firstname', 'lastname', 'email', 'subject', 'message']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        clean_email(email)
        return email
