import json
import os
from datetime import datetime

from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView

from events.models import Events, Volunteer
from ext_libs.rave.payment import RavePaymentHandler
from mainsite.models import (GalleryImage, PaymentSubscription,
                             TransactionHistory)
from user.models import UserProfile
from utils.enums import PaymentPlanStatus, TransactionStatus
from utils.views import (custom_paginator, generate_hashed_string,
                         get_actual_template)


def home(request):
    volunteers = Volunteer.objects.all().order_by("?")[:4]
    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    number_of_donations = len(list(TransactionHistory.objects.all()))
    events = len(list(Events.objects.filter(event_date__lt=datetime.now())))
    context = {
        'total_amount': total_transaction.get('amount'),
        'events_done': events,
        'total_transaction': number_of_donations,
        'volunteers': volunteers
    }
    # return HttpResponse('welcome to feed someone')
    return render(request, 'home.html', context)


def about(request):
    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    transacters = len(list(TransactionHistory.objects.all()))
    total_volunteers = len(list(UserProfile.objects.all()))
    context = {
        'total_amount': total_transaction.get('amount'),
        'total_volunteers': total_volunteers,
        'total_transaction': transacters,
    }
    # return HttpResponse('welcome to feed someone')
    return render(request, 'about.html', context)


# Post Page Fxn recreated into a class
class AllGalleryImagesListView(ListView):
    model = GalleryImage
    template_name = 'mainsite/gallery_list.html'
    context_object_name = 'objects'
    ordering = ['-date_posted']
    paginate_by = 8

    def get_template_names(self):
        template_names = super().get_template_names()
        return get_actual_template(self, 'mainsite/gallery_ajax.html') + template_names

    def paginate_queryset(self, queryset, page_size):
        return custom_paginator(self.request, page_size, queryset)


# Post Page Fxn recreated into a class
# convert into an inclusion tag and dynamically generate the images
class FooterGalleryImages(ListView):
    model = GalleryImage
    template_name = 'gallery_list.html'
    context_object_name = 'event_imgs'
    ordering = ['?', '-date_posted']
    paginate_by = 6


@csrf_exempt
def upload_images(request):
    if request.method == 'POST':
        event = request.POST['event']
        if event:
            response = {'files': []}
            # Loop through our files in the files list uploaded
            for image in request.FILES.getlist('files[]'):
                # Create a new entry in our database
                new_image = GalleryImage()
                # Save the image using the model's ImageField settings
                filename, ext = os.path.splitext(image.name)
                new_image.image.save(f"{image.name}-{datetime.now()}{ext}", image)
                new_image.image_title = filename
                new_image.event_id = event
                new_image.save()
                # Save output for return as JSON
                response['files'].append({
                    'name': '%s' % image.name,
                    'size': '%d' % image.size,
                    'url': '%s' % new_image.image.url,
                    'thumbnailUrl': '%s' % new_image.image.url,
                    'deleteUrl': r'\/image\/delete\/%s' % image.name,
                    "deleteType": 'DELETE'
                })

            return HttpResponse(json.dumps(response), content_type='application/json')
    else:
        event = Events.objects.all()
        return render(request, 'file_upload.html', {'event': event})


def donate_thanks(request):
    query_dict = request.GET
    if query_dict:
        status = query_dict.get('status')
        tx_ref = query_dict.get('tx_ref')
        tr_id = query_dict.get('transaction_id')
        print(status, tx_ref, tr_id)
        # # cannot remember why this is like this, will check it out when I want to extend payment
        # rave = Rave("FLWPUBK-ef604c855317a5fd377639a5a6744efe-X",
        #             "FLWSECK-439f20374599e622cf6b0b03bacf2793-X",
        #             usingEnv=False, production=True)
        # if status == 'successful':
        #     res = rave.Card.verify(tx_ref)
        #     amount = res.get('amount')
        # else:
        #     messages.info(request, 'PAYMENT UNSUCCESSFUL AND REVERSED')
        #     return redirect('mainsite:donate')
        # transaction = TransactionHistory.objects.create(
        #     status=status, tx_ref=tx_ref, tr_id=tr_id, amount=amount)
        # transaction.save()
    return render(request, 'thanks-donation.html')


def donate(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        currency = request.POST.get('currency')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        tx_ref_id = generate_hashed_string({"first_name": first_name, "last_name": last_name, "email": email})

        # Initialize the payment handler
        handler = RavePaymentHandler(os.environ.get("RAVE_SECRET_KEY"), os.environ.get("RAVE_PUBLIC_KEY"))

        # Check the flag from the frontend (e.g., 'payment_type' field)
        payment_type = request.POST.get('payment_type')
        customer_data = {"first_name": first_name, "last_name": last_name, "email": email}

        if payment_type == 'one_time':
            response_data = handler.pay_once(amount, currency, customer_data, tx_ref_id)
            subscription = None
        elif payment_type == 'recurrent':
            # Handle recurrent payment
            subscription_name = request.POST.get('subscription_name')
            subscription_interval = request.POST.get('subscription_interval')
            subscription_duration = int(request.POST.get('subscription_duration'))
            response_data = handler.pay_recurrent(amount, currency, customer_data, tx_ref_id, subscription_name,
                                                  subscription_interval, subscription_duration)
            subscription = PaymentSubscription.objects.create(
                plan_id=response_data.get('plan_id', ''),
                plan_status=PaymentPlanStatus.CREATED.value,
                plan_name=subscription_name,
                plan_duration=subscription_duration
            )
        else:
            return HttpResponse("Invalid payment type")

        tx_history = TransactionHistory.objects.create(
            tx_status=TransactionStatus.PENDING.value,
            tx_ref=tx_ref_id,
            tr_id=response_data.get('transaction_id', ''),
            amount=amount)
        if subscription:
            tx_history.subscription = subscription
            tx_history.save()
        return redirect(response_data['link'])
    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    transactors = len(list(TransactionHistory.objects.all())) - 2
    total_volunteers = len(list(UserProfile.objects.all()))
    context = {
        'total_amount': total_transaction.get('amount'),
        'total_volunteers': total_volunteers,
        'total_transaction': transactors,
    }
    return render(request, 'donate-copy.html', context)


def webhooks(request):
    # check for successful webhooks so we can email the donor updates about
    # what we achieved and failed webhooks so we can remind them to try again
    status = request.GET['status']
    tx_ref = request.GET['tx_ref']
    tx_id = request.GET['transaction_id']
    print(f'{status=} {tx_id=} {tx_ref=}')
    print(request.GET)
    print(request.GET.__dict__)
    return redirect('/')


def callback(request):
    pass


def services(request):
    pass


def privacy(request):
    return render(request, 'privacy.html')
