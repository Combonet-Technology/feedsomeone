from django.forms import ModelForm

from contact.models import Contact


class ContactForm(ModelForm):
    class Meta:
        model = Contact
        fields = ['firstname', 'lastname', 'email', 'subject', 'message']
