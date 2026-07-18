import logging

from django.contrib import messages
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView

from .forms import VacancyApplicationForm
from .models import Vacancy, VacancyApplication
from .notifications import notify_new_application

logger = logging.getLogger(__name__)


class VacancyListView(ListView):
    model = Vacancy
    context_object_name = 'vacancies'
    template_name = 'opportunities/vacancy_list.html'

    def get_queryset(self):
        return Vacancy.objects.filter(is_active=True).exclude(status='draft').annotate(
            status_order=Case(
                When(status='open', then=Value(0)),
                When(status='filled', then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by('status_order', 'display_order', '-published_at', '-created_at')


class VacancyDetailView(DetailView):
    model = Vacancy
    context_object_name = 'vacancy'
    template_name = 'opportunities/vacancy_detail.html'

    def get_queryset(self):
        return Vacancy.objects.filter(is_active=True).exclude(status='draft')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        initial = {}
        if self.request.user.is_authenticated:
            initial = {
                'full_name': self.request.user.get_full_name(),
                'email': self.request.user.email,
            }
        context['application_form'] = VacancyApplicationForm(initial=initial)
        context['already_applied'] = (
            self.request.user.is_authenticated
            and VacancyApplication.objects.filter(
                vacancy=self.object,
                applicant=self.request.user,
            ).exists()
        )
        return context


def apply(request, slug):
    vacancy = get_object_or_404(
        Vacancy.objects.exclude(status='draft'),
        slug=slug,
        is_active=True,
    )
    if not vacancy.is_open:
        messages.info(request, 'This opportunity is not currently accepting applications.')
        return redirect(vacancy.get_absolute_url())

    form = VacancyApplicationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        duplicate = VacancyApplication.objects.filter(
            vacancy=vacancy,
            email__iexact=form.cleaned_data['email'],
        )
        if request.user.is_authenticated:
            duplicate = duplicate | VacancyApplication.objects.filter(
                vacancy=vacancy,
                applicant=request.user,
            )
        if duplicate.exists():
            messages.info(request, 'An application for this role has already been received from you.')
            return redirect(vacancy.get_absolute_url())

        application = form.save(commit=False)
        application.vacancy = vacancy
        if request.user.is_authenticated:
            application.applicant = request.user
        application.save()
        try:
            notify_new_application(
                application,
                site_url=request.build_absolute_uri('/'),
                admin_url=request.build_absolute_uri(
                    reverse(
                        'admin:opportunities_vacancyapplication_change',
                        args=(application.pk,),
                    )
                ),
            )
        except Exception:
            logger.exception(
                'Unexpected vacancy notification failure for application %s',
                application.pk,
            )
        messages.success(request, 'Your application has been received.')
        return redirect(vacancy.get_absolute_url())

    return render(request, 'opportunities/vacancy_detail.html', {
        'vacancy': vacancy,
        'application_form': form,
        'already_applied': False,
    })
