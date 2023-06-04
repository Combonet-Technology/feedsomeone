import json
import os
from datetime import datetime

from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView

from events.models import Events, Volunteer
from mainsite.models import GalleryImage, TransactionHistory
from rave_python import Rave
from user.models import UserProfile


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


# def contact(request):
#     return render(request, 'contact.html')


# Post Page Fxn recreated into a class
class AllGalleryImagesListView(ListView):
    model = GalleryImage
    context_object_name = 'objects'
    ordering = ['-date_posted']
    paginate_by = 8

    def get_template_names(self):
        if self.request.is_ajax():
            return ['mainsite/gallery_ajax.html']
        else:
            return ['mainsite/gallery_list.html']

    def paginate_queryset(self, queryset, page_size):
        paginator = Paginator(queryset, page_size)
        page = self.request.GET.get('page')
        print(f'page gotten is {page} and of type {type(page)}')
        try:
            results = paginator.page(page)
        except PageNotAnInteger:
            print('got first page')
            results = paginator.page(1)
        except EmptyPage:
            print('AJAX request')
            if self.request.is_ajax():
                print('No more pics')
                return HttpResponse('')
            results = paginator.page(paginator.num_pages)

        is_paginated = len(results) > 0

        return paginator, page, results, is_paginated,

    # def get_context_data(self, *, object_list=None, **kwargs):
    #     context = super().get_context_data(**kwargs)


# Post Page Fxn recreated into a class
# convert into an inclusion tag and dynamically generate the images
class FooterGalleryImages(ListView):
    model = GalleryImage
    template_name = 'gallery_list.html'
    context_object_name = 'event_imgs'
    ordering = ['?', '-date_posted']
    paginate_by = 6


# class SinglePostDetailView(DetailView):
#     model = GalleryImage
#     # template_name = 'article_detail.html'
#     context_object_name = 'event_imgs'


def donate(request):
    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    transacters = len(list(TransactionHistory.objects.all())) - 2
    total_volunteers = len(list(UserProfile.objects.all()))
    context = {
        'total_amount': total_transaction.get('amount'),
        'total_volunteers': total_volunteers,
        'total_transaction': transacters,
    }
    return render(request, 'donate.html', context)


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
        # cannot remember why this is like this, will check it out when I want to extend payment
        rave = Rave("FLWPUBK-ef604c855317a5fd377639a5a6744efe-X",
                    "FLWSECK-439f20374599e622cf6b0b03bacf2793-X",
                    usingEnv=False, production=True)
        if status == 'successful':
            res = rave.Card.verify(tx_ref)
            amount = res.get('amount')
        else:
            messages.info(request, 'PAYMENT UNSUCCESSFUL AND REVERSED')
            return redirect('mainsite:donate')
        transaction = TransactionHistory.objects.create(
            status=status, tx_ref=tx_ref, tr_id=tr_id, amount=amount)
        transaction.save()
    return render(request, 'thanks-donation.html')


def webhooks(request):
    pass


def callback(request):
    pass


def services(request):
    pass


def privacy(request):
    return render(request, 'privacy.html')
