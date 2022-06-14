from django.core.mail import send_mail, BadHeaderError
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import Contact


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
            new_message = Contact.objects.create(firstname=firstname,
                                                 lastname=lastname,
                                                 email=email,
                                                 subject=subject,
                                                 message=message)
            try:
                if send_mail('FEEDSOMEONE CONTACT FORM',
                             plain_message,
                             'femolak@outlook.com',
                             [to],
                             html_message=html_message,
                             fail_silently=False, ):
                    new_message.received = True
                new_message.save()
            except BadHeaderError as e:
                return HttpResponse("Message sending failed because of this error: ", str(e), "\n\nMessage scheduled to be "
                                                                                              "resent later")
            except Exception as e:
                return HttpResponse("Message sending failed because of this error: ", str(e), "\n\nMessage scheduled to be "
                                                                                              "resent later")
            data = {
                'subject': 'Thank You!',
                'title': 'Feedsomeone - contact form response',
                'msg': """<strong>Your email has been received</strong> and you will be replied to shortly."""
            }
            return render(request, 'thank-you.html', data)
        else:
            messages.info(request, 'please fill make sure all fields are filled appropriately')
            return redirect('contact')
    else:
        return render(request, 'contact.html', {'message': message})


def thanks(request):
    return render(request, 'thank-you.html')
