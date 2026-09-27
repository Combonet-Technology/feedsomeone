"""Recruitment intake: vacancy availability and application batch identity."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .models import Vacancy, VacancyApplication


def has_duplicate_application(*, vacancy_id, cohort_id, email, applicant_id=None, exclude_pk=None):
    identity = Q(email__iexact=email)
    if applicant_id:
        identity |= Q(applicant_id=applicant_id)
    return VacancyApplication.objects.filter(
        identity, vacancy_id=vacancy_id, cohort_id=cohort_id,
    ).exclude(pk=exclude_pk).exists()


@transaction.atomic
def submit_application(application):
    # Cohort closure updates these same vacancy rows, serialising intake with closure.
    vacancy = Vacancy.objects.select_for_update().get(pk=application.vacancy_id)
    if not vacancy.is_open:
        raise ValidationError('This opportunity is not currently accepting applications.')
    application.vacancy = vacancy
    application.cohort_id = vacancy.cohort_id
    if has_duplicate_application(
        vacancy_id=vacancy.pk, cohort_id=vacancy.cohort_id,
        email=application.email, applicant_id=application.applicant_id,
    ):
        raise ValidationError('An application for this role has already been received from you.')
    application.save()
    return application
