from django.core.mail import send_mail, BadHeaderError
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import Contact
from django.contrib.auth.decorators import login_required
# Create your views here.


# @login_required()
def contact(request):
    message = Contact()

    if request.method == 'POST':
        firstname = request.POST['first_name']
        lastname = request.POST['last_name']
        email = request.POST['email']
        subject = request.POST['subject']
        message = request.POST['message']
        if email != '' and subject != '' and firstname != '' and message != '':
            context = {
                'sender': email,
                'fname': firstname,
                'lname': lastname,
                'detail': message,
                'title': subject,
            }
            html_message = render_to_string('new_email.html', context)
            plain_message = strip_tags(html_message)
            from_email = email
            to = 'femolak@outlook.com'
            try:
                if send_mail('FEEDSOMEONE CONTACT FORM',
                             plain_message,
                             'femolak@outlook.com',
                             [to],
                             html_message=html_message,
                             fail_silently=False, ):
                    messages.info(request, 'Mail sent Successfully')
            except BadHeaderError:
                return HttpResponse('Invalid header found.')
            return HttpResponseRedirect('contact/thanks')

            new_message = Contact.objects.create(firstname=firstname,
                                                 lastname=lastname,
                                                 email=email,
                                                 subject=subject,
                                                 message=message)
            new_message.save()
            return redirect('/')
        else:
            messages.info(request, 'please fill make sure all fields are filled appropriately')
            return redirect('contact')
    else:
        return render(request, 'contact.html', {'message': message})


def thanks(request):
    return render(request, 'thank-you.html')