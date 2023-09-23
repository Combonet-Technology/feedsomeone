import json
import os
from datetime import datetime

from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView

from events.models import Events, Volunteer
from ext_libs.rave.payment import RavePaymentHandler
from mainsite.models import GalleryImage, TransactionHistory
from mainsite.utils import (create_transaction_history, get_or_create_donor,
                            get_or_create_user_profile,
                            handle_failed_transaction,
                            handle_one_time_donation,
                            handle_recurrent_donation,
                            handle_successful_transaction)
from user.models import UserProfile
from utils.enums import SubscriptionPlan, TransactionStatus
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


def donate(request):
    handler = RavePaymentHandler(os.environ.get("RAVE_SECRET_KEY"), os.environ.get("RAVE_PUBLIC_KEY"))
    print(f'{handler=}')
    if request.method == 'POST':
        return handle_donation_post(request, handler)

    if request.method == 'GET':
        return handle_donation_get(request, handler)

    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    transactors = len(list(TransactionHistory.objects.all())) - 2
    total_volunteers = len(list(UserProfile.objects.all()))
    context = {
        'total_amount': total_transaction.get('amount'),
        'total_volunteers': total_volunteers,
        'total_transaction': transactors,
    }
    return render(request, 'donate-draft.html', context)


def handle_donation_post(request, handler):
    amount = request.POST.get('amount')
    currency = request.POST.get('currency')
    full_name = request.POST.get('full_name')
    email = request.POST.get('email')
    donation_type = request.POST.get('donation_type')
    print(amount, currency, full_name, email, donation_type)
    customer_data = {"full_name": full_name, "email": email}
    names = full_name.split(' ')
    first_name = names[0]
    last_name = ' '.join(names[1:])
    user_profile = get_or_create_user_profile(email, first_name, last_name)
    donor = get_or_create_donor(user_profile)

    tx_ref_id = generate_hashed_string(customer_data)
    assert email is not None, "Email cannot be None"

    if donation_type == SubscriptionPlan.ONE_TIME.value:
        response_data, subscription = handle_one_time_donation(handler, amount, currency, customer_data, tx_ref_id)
    elif donation_type in ['monthly', 'quarterly', 'annually']:
        response_data, subscription = handle_recurrent_donation(
            handler, amount, currency, customer_data, tx_ref_id, full_name, donation_type
        )
    else:
        return HttpResponse("Invalid payment type")

    create_transaction_history(TransactionStatus.PENDING.value, tx_ref_id, amount, donor, subscription, currency)
    print(f'{response_data=}')
    return redirect(response_data['data']['link'])


def handle_donation_get(request, handler):
    query_dict = request.GET
    if query_dict:
        status = query_dict.get('status')
        tx_ref = query_dict.get('tx_ref')
        tr_id = query_dict.get('transaction_id')
        transaction = TransactionHistory.objects.get(tx_ref=tx_ref)
        transaction.tr_id = tr_id

        if status == TransactionStatus.SUCCESSFUL.value:
            handle_successful_transaction(handler, transaction)
            return render(request, 'thanks-donation.html')
        else:
            handle_failed_transaction(transaction)
            messages.info(request, 'PAYMENT UNSUCCESSFUL AND REVERSED')
            return redirect('mainsite:donate')
    return render(request, 'donate-draft.html')


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
