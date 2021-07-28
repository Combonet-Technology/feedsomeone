import json
import os
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, DetailView, CreateView
from mainsite.models import GalleryImage, Events, TransactionHistory
from rave_python import Rave
from django.urls import reverse_lazy
from user.models import Profile
from django.db.models import Sum


# Create your views here.
def home(request):
    volunteers = Profile.objects.exclude(active=False).order_by("?")[:4]
    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    transacters = len(list(TransactionHistory.objects.all())) - 2
    total_volunteers = len(list(Profile.objects.all()))
    context = {
        'total_amount': total_transaction.get('amount'),
        'total_volunteers': total_volunteers,
        'total_transaction': transacters,
        'volunteers': volunteers
    }
    # return HttpResponse('welcome to feed someone')
    return render(request, 'home.html', context)


def about(request):
    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    transacters = len(list(TransactionHistory.objects.all())) - 2
    total_volunteers = len(list(Profile.objects.all()))
    context = {
        'total_amount': total_transaction.get('amount'),
        'total_volunteers': total_volunteers,
        'total_transaction': transacters,
    }
    # return HttpResponse('welcome to feed someone')
    return render(request, 'about.html', context)


class AllEventsList(ListView):
    model = Events
    template_name = 'events.html'
    context_object_name = 'events'
    ordering = ['event_date']
    paginate_by = 4


class UpcomingEventsList(ListView):
    model = Events
    template_name = 'events.html'
    context_object_name = 'events'
    ordering = ['event_date']
    paginate_by = 2

    def get_queryset(self):
        current_date = datetime.today()
        return Events.objects.filter(event_date__gt=current_date).order_by('-event_date')

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context['page_title_head'] = "Upcoming Charity Events"
        context['page_title_sub'] = "Events Coming Soon"
        context['page_title_content'] = "Where We Will Be Impacting In The Coming Weeks"
        return context


class PastEventsList(ListView):
    model = Events
    template_name = 'events.html'
    context_object_name = 'events'
    ordering = ['event_date']
    paginate_by = 2

    def get_queryset(self):
        current_date = datetime.today()
        return Events.objects.filter(event_date__lt=datetime.today()).order_by('-event_date')

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context['page_title_head'] = "Organized Charity Events"
        context['page_title_sub'] = "Events we did in the past"
        context['page_title_content'] = "Events we have organized in the Past"
        return context


class EventDetailView(DetailView):
    model = Events
    # template_name = 'post_detail.html'
    context_object_name = 'event'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        volunteers = Profile.objects.exclude(active=False).order_by('date_joined')[:6]
        context['volunteers'] = volunteers
        return context

class CreateEventView(LoginRequiredMixin, CreateView):
    model = Events
    fields = ['title', 'event_date', 'time', 'location','feature_img','content','budget']
    success_url = '/events/upcoming'
    # success_url = reverse_lazy('future-events')

    def form_valid(self, form):
        form.instance.event_author = self.request.user
        return super(CreateEventView, self).form_valid(form)

# def contact(request):
#     return render(request, 'contact.html')


# Post Page Fxn recreated into a class
class AllGalleryImagesListView(ListView):
    model = GalleryImage
    template_name = 'gallery.html'
    context_object_name = 'event_imgs'
    ordering = ['?','-date_posted']
    paginate_by = 12


# Post Page Fxn recreated into a class
class FooterGalleryImages(ListView):
    model = GalleryImage
    template_name = 'gallery.html'
    context_object_name = 'event_imgs'
    ordering = ['?','-date_posted']
    paginate_by = 6


# class SinglePostDetailView(DetailView):
#     model = GalleryImage
#     # template_name = 'post_detail.html'
#     context_object_name = 'event_imgs'


def donate(request):
    total_transaction = TransactionHistory.objects.aggregate(amount=Sum('amount'))
    transacters = len(list(TransactionHistory.objects.all()))-2
    total_volunteers = len(list(Profile.objects.all()))
    context = {
        'total_amount': total_transaction.get('amount'),
        'total_volunteers': total_volunteers,
        'total_transaction': transacters,
    }
    return render(request, 'donate.html', context)


@csrf_exempt
def upload_images(request):
    if request.method == 'POST':
        response = {'files': []}
        # Loop through our files in the files list uploaded
        for image in request.FILES.getlist('files[]'):
            # Create a new entry in our database
            new_image = GalleryImage()
            # Save the image using the model's ImageField settings
            filename, ext = os.path.splitext(image.name)
            new_image.image.save("%s-%s%s" % (image.name, datetime.now(), ext), image)
            new_image.image_title = filename
            new_image.event_id = request.POST['event']
            new_image.save()
            # Save output for return as JSON
            response['files'].append({
                'name': '%s' % image.name,
                'size': '%d' % image.size,
                'url': '%s' % new_image.image.url,
                'thumbnailUrl': '%s' % new_image.image.url,
                'deleteUrl': '\/image\/delete\/%s' % image.name,
                "deleteType": 'DELETE'
            })

        return HttpResponse(json.dumps(response), content_type='application/json')
    else:
        event = Events.objects.all()
        return render(request, 'file_upload.html', {'event':event})


def donate_thanks(request):
    query_dict = request.GET
    if query_dict:
        status = query_dict.get('status')
        tx_ref = query_dict.get('tx_ref')
        tr_id = query_dict.get('transaction_id')
        rave = Rave("FLWPUBK-ef604c855317a5fd377639a5a6744efe-X", "FLWSECK-439f20374599e622cf6b0b03bacf2793-X",
                    usingEnv=False, production=True)
        if status == 'successful':
            res = rave.Card.verify(tx_ref)
            amount = res.get('amount')
        else:
            messages.info(request, 'PAYMENT UNSUCCESSFUL AND REVERSED')
            return redirect('donate')
        transaction = TransactionHistory.objects.create(status=status, tx_ref=tx_ref, tr_id=tr_id, amount=amount)
        transaction.save()
    return render(request, 'thanks-donation.html')
