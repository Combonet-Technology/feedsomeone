from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.urls import reverse

from .storage import VacancyCVStorage, VacancyPrivateDocumentStorage


def vacancy_cv_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f'vacancy_applications/private_cv/{uuid4().hex}{extension}'


def volunteer_offer_upload_to(instance, filename):
    extension = Path(filename).suffix.lower() or '.pdf'
    return f'vacancy_applications/private_offers/{uuid4().hex}{extension}'


vacancy_cv_storage = VacancyCVStorage()
vacancy_offer_storage = VacancyPrivateDocumentStorage()


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
        ('offered', 'Offered'),
        ('offer_accepted', 'Offer accepted'),
        ('agreement_signed', 'Agreement signed'),
        ('onboarding', 'Onboarding'),
        ('active', 'Active'),
        ('not_selected', 'Not selected'),
        ('withdrawn', 'Withdrawn'),
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
        permissions = (
            ('send_volunteer_offer', 'Can prepare and send volunteer offers'),
        )
        constraints = [
            models.UniqueConstraint(fields=('vacancy', 'applicant'), name='unique_vacancy_applicant'),
            models.UniqueConstraint(fields=('vacancy', 'email'), name='unique_vacancy_email'),
        ]

    def __str__(self):
        return f'{self.full_name} - {self.vacancy}'


class VolunteerOffer(models.Model):
    DELIVERY_STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    )

    application = models.OneToOneField(
        VacancyApplication,
        on_delete=models.CASCADE,
        related_name='volunteer_offer',
    )
    recipient_name = models.CharField(max_length=255)
    recipient_email = models.EmailField()
    role_title = models.CharField(max_length=255)
    letter_date = models.DateField()
    start_date = models.DateField()
    initial_period = models.CharField(max_length=120)
    weekly_commitment = models.CharField(max_length=160)
    work_arrangement = models.TextField()
    reporting_contact = models.CharField(max_length=255)
    role_contribution = models.TextField()
    acceptance_deadline = models.DateField(null=True, blank=True)
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='draft',
    )
    delivery_key = models.UUIDField(default=uuid4, unique=True, editable=False)
    letter_pdf = models.FileField(
        storage=vacancy_offer_storage,
        upload_to=volunteer_offer_upload_to,
        blank=True,
    )
    brevo_message_id = models.CharField(max_length=255, blank=True, editable=False)
    delivery_error = models.TextField(blank=True, editable=False)
    sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='volunteer_offers_sent',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Offer for {self.recipient_name} - {self.role_title}'
