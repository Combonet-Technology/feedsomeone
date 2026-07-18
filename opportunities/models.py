from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.urls import reverse

from .storage import VacancyCVStorage


def vacancy_cv_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f'vacancy_applications/private_cv/{uuid4().hex}{extension}'


vacancy_cv_storage = VacancyCVStorage()


class Vacancy(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('filled', 'Filled'),
        ('closed', 'Closed'),
    )
    ENGAGEMENT_TYPE_CHOICES = (
        ('volunteer', 'Volunteer core team'),
        ('internship', 'Internship'),
        ('contract', 'Contract'),
        ('staff', 'Staff'),
    )
    WORK_MODE_CHOICES = (
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
        ('onsite', 'On-site'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)
    team = models.CharField(max_length=120, blank=True)
    summary = models.CharField(max_length=500)
    about_oef = models.TextField(blank=True)
    description = models.TextField()
    expectations = models.TextField()
    responsibilities = models.TextField()
    benefits = models.TextField()
    who_we_are_looking_for = models.TextField()
    engagement_type = models.CharField(
        max_length=20,
        choices=ENGAGEMENT_TYPE_CHOICES,
        default='volunteer',
    )
    work_mode = models.CharField(
        max_length=20,
        choices=WORK_MODE_CHOICES,
        default='remote',
    )
    location = models.CharField(max_length=160, default='Nigeria')
    time_commitment = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    positions_available = models.PositiveSmallIntegerField(default=1)
    display_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    catalogue_version = models.PositiveSmallIntegerField(default=0, editable=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-published_at', '-created_at')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('opportunities:detail', kwargs={'slug': self.slug})

    @property
    def is_open(self):
        return self.is_active and self.status == 'open'

    @staticmethod
    def _list_items(value):
        return tuple(
            line.lstrip('- ').strip()
            for line in value.splitlines()
            if line.lstrip('- ').strip()
        )

    @property
    def responsibility_items(self):
        return self._list_items(self.responsibilities)

    @property
    def expectation_items(self):
        return self._list_items(self.expectations)

    @property
    def benefit_items(self):
        return self._list_items(self.benefits)


class VacancyApplication(models.Model):
    STATUS_CHOICES = (
        ('received', 'Received'),
        ('reviewing', 'Reviewing'),
        ('shortlisted', 'Shortlisted'),
        ('closed', 'Closed'),
    )
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='vacancy_applications',
        null=True,
        blank=True,
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    cv = models.FileField(
        storage=vacancy_cv_storage,
        upload_to=vacancy_cv_upload_to,
    )
    cover_letter = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    acknowledgement_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    slack_notified_at = models.DateTimeField(null=True, blank=True, editable=False)
    newsletter_opt_in = models.BooleanField(default=False)
    newsletter_subscribed_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    notification_error = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=('vacancy', 'applicant'), name='unique_vacancy_applicant'),
            models.UniqueConstraint(fields=('vacancy', 'email'), name='unique_vacancy_email'),
        ]

    def __str__(self):
        return f'{self.full_name} - {self.vacancy}'
