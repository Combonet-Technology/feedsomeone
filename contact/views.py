import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import BadHeaderError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from ext_libs.sendgrid.sengrid import send_email

from .forms import ContactForm
from .models import Contact

logger = logging.getLogger(__name__)


def contact(request):
    if request.method == 'POST':
        contact_form = ContactForm(request.POST)
        if contact_form.is_valid():
            new_message = contact_form.save(commit=False)
            context = {
                'sender': contact_form.data.get('email'),
                'fname': contact_form.data.get('firstname'),
                'lname': contact_form.data.get('lastname'),
                'detail': contact_form.data.get('message'),
                'title': contact_form.data.get('subject'),
            }
            try:
                send_email(source=settings.EMAIL_HOST_USER, destination=settings.GMAIL_EMAIL,
                           subject='FEEDSOMEONE CONTACT FORM', content=render_to_string('new_email.html', context))
                new_message.received = True
            except BadHeaderError as e:
                new_message.received = False
                return HttpResponse("Message sending failed because of this error: ", str(e),
                                    "\n\nMessage scheduled to be resent later")
            except Exception as e:
                new_message.received = True
                logger.log(level=logging.ERROR, msg=f'Error sending mail: {str(e)}')
            finally:
                new_message.save()
            data = {
                'subject': 'Thank You!',
                'title': 'Feedsomeone - contact form response',
                'msg': """<strong>Your email has been received</strong> and you will be replied to shortly."""
            }
            return render(request, 'thank-you.html', data)
        else:
            messages.info(request, 'please fill make sure all fields are filled appropriately \n', contact_form.errors)
            return redirect('contact')
    else:
        return render(request, 'contact.html', {'message': Contact()})


def thanks(request):
    return render(request, 'thank-you.html')
