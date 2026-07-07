from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, DetailView, ListView

from events.models import Events
from mainsite.services.cloudinary_gallery import (get_gallery_assets,
                                                  get_gallery_definition,
                                                  resolve_event_gallery_slug)
from user.models import Volunteer


class AllEventsList(ListView):
    model = Events
    template_name = 'events.html'
    context_object_name = 'events'
    ordering = ['event_date']
    paginate_by = 4

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title_head'] = "Programmes and Events"
        context['page_title_sub'] = "OEF programme pipeline"
        context['page_title_content'] = "Completed outreach and planned work"
        context['page_intro'] = (
            "Explore OEF's documented outreach history and the programme areas "
            "we are formalising for future grants and partnerships."
        )
        return context


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
        context['page_title_head'] = "Upcoming Programmes"
        context['page_title_sub'] = "Planned work"
        context['page_title_content'] = "Future relief, learning, health and dignity projects"
        context['page_intro'] = (
            "Upcoming records represent planned or proposed activities. We keep them "
            "separate from completed impact until delivery is verified."
        )
        return context


class PastEventsList(ListView):
    model = Events
    template_name = 'events.html'
    context_object_name = 'events'
    ordering = ['event_date']
    paginate_by = 2

    def get_queryset(self):
        return Events.objects.filter(event_date__lt=datetime.today()).order_by('-event_date')

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context['page_title_head'] = "Past Outreach"
        context['page_title_sub'] = "Completed work"
        context['page_title_content'] = "Documented Feed Someone and OEF outreach history"
        context['page_intro'] = (
            "These records describe completed activities and link to approved "
            "evidence where available."
        )
        return context


class EventDetailView(DetailView):
    # queryset = None
    slug_field = 'event_slug'
    slug_url_kwarg = 'slug'
    pk_url_kwarg = 'pk'
    query_pk_and_slug = True
    model = Events
    context_object_name = 'event'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        volunteers = Volunteer.objects.all().order_by('user__date_joined')[:6]
        context['volunteers'] = volunteers
        gallery_slug = resolve_event_gallery_slug(
            self.object.event_slug or '',
            self.object.title or '',
        )
        context['gallery_slug'] = gallery_slug
        context['gallery'] = get_gallery_definition(gallery_slug) if gallery_slug else None
        context['gallery_assets'] = get_gallery_assets(gallery_slug) if gallery_slug else []
        return context


class CreateEventView(LoginRequiredMixin, CreateView):
    model = Events
    fields = ['title', 'event_date', 'time', 'location', 'feature_img', 'content', 'budget']
    success_url = '/events/upcoming'

    # success_url = reverse_lazy('future-events')

    def form_valid(self, form):
        form.instance.event_author = self.request.user
        return super().form_valid(form)
