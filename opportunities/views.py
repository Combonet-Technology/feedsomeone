from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from .forms import VacancyApplicationForm
from .models import Vacancy, VacancyApplication


class VacancyListView(ListView):
    model = Vacancy
    context_object_name = 'vacancies'
    template_name = 'opportunities/vacancy_list.html'

    def get_queryset(self):
        return Vacancy.objects.filter(is_active=True).order_by('-published_at', '-created_at')


class VacancyDetailView(DetailView):
    model = Vacancy
    context_object_name = 'vacancy'
    template_name = 'opportunities/vacancy_detail.html'

    def get_queryset(self):
        return Vacancy.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['application_form'] = VacancyApplicationForm()
        context['already_applied'] = (
            self.request.user.is_authenticated and
            VacancyApplication.objects.filter(vacancy=self.object, applicant=self.request.user).exists()
        )
        return context


@login_required
def apply(request, slug):
    vacancy = get_object_or_404(Vacancy, slug=slug, is_active=True)
    if VacancyApplication.objects.filter(vacancy=vacancy, applicant=request.user).exists():
        messages.info(request, 'You have already applied for this vacancy.')
        return redirect(vacancy.get_absolute_url())

    form = VacancyApplicationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        application = form.save(commit=False)
        application.vacancy = vacancy
        application.applicant = request.user
        application.save()
        messages.success(request, 'Your application has been received.')
        return redirect(vacancy.get_absolute_url())

    return render(request, 'opportunities/vacancy_detail.html', {
        'vacancy': vacancy,
        'application_form': form,
        'already_applied': False,
    })
