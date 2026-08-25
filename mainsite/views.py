import os
from datetime import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import ListView

from events.models import Events
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
from utils.views import generate_hashed_string


def home(request):
    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    number_of_donations = TransactionHistory.objects.count()
    events = Events.objects.filter(event_date__lt=datetime.now()).count()
    context = {
        'total_amount': total_transaction.get('amount'),
        'events_done': events,
        'total_transaction': number_of_donations,
    }
    # return HttpResponse('welcome to feed someone')
    return render(request, 'home.html', context)


def about(request):
    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    transacters = TransactionHistory.objects.count()
    total_volunteers = UserProfile.objects.count()
    context = {
        'total_amount': total_transaction.get('amount'),
        'total_volunteers': total_volunteers,
        'total_transaction': transacters,
    }
    # return HttpResponse('welcome to feed someone')
    return render(request, 'about.html', context)


def what_is_oef(request):
    return render(request, 'what-is-oef.html')


def impact(request):
    events = Events.objects.filter(event_date__lte=datetime.now()).order_by('event_date', 'title')
    page_obj = Paginator(events, 6).get_page(request.GET.get('page'))
    return render(request, 'impact.html', {
        'events': page_obj.object_list,
        'page_obj': page_obj,
    })


def transparency(request):
    return render(request, 'transparency.html')


def robots_txt(request):
    content = "User-agent: *\nAllow: /\nSitemap: https://www.oluwafemiebenezerfoundation.org/sitemap.xml\n"
    return HttpResponse(content, content_type='text/plain')


# Post Page Fxn recreated into a class
# convert into an inclusion tag and dynamically generate the images
class FooterGalleryImages(ListView):
    model = GalleryImage
    template_name = 'gallery_list.html'
    context_object_name = 'event_imgs'
    ordering = ['?', '-date_posted']
    paginate_by = 6


def upload_images(request):
    messages.info(request, 'Event image uploads have moved to the event administration area.')
    return redirect('admin:events_events_changelist')


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
    return render(request, 'terms_of_service.html')


def privacy(request):
    return render(request, 'privacy.html')
