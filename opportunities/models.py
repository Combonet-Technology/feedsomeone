from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone

from utils.cloudinary_paths import cloudinary_folder

from .storage import VacancyCVStorage, VacancyPrivateDocumentStorage


def vacancy_cv_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f'{cloudinary_folder("vacancy-applications", "private-cv")}/{uuid4().hex}{extension}'


def volunteer_offer_upload_to(instance, filename):
    extension = Path(filename).suffix.lower() or '.pdf'
    return f'{cloudinary_folder("vacancy-applications", "private-offers")}/{uuid4().hex}{extension}'


vacancy_cv_storage = VacancyCVStorage()
vacancy_offer_storage = VacancyPrivateDocumentStorage()


class RecruitmentCohort(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        OPEN = 'open', 'Open'
        INTAKE_CLOSED = 'intake_closed', 'Closed'
        COMPLETED = 'completed', 'Completed'

    code = models.SlugField(unique=True, max_length=60)
    name = models.CharField(max_length=160)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    opened_at = models.DateTimeField(null=True, blank=True, editable=False)
    intake_closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.code})'

    def clean(self):
        if self.pk and type(self).objects.filter(pk=self.pk).exclude(code=self.code).exists():
            raise ValidationError({'code': 'The cohort code cannot change.'})
        if self.pk and self.applications.exists():
            original_name = type(self).objects.filter(pk=self.pk).values_list('name', flat=True).first()
            if self.name != original_name:
                raise ValidationError({'name': 'The cohort name cannot change after applications exist.'})

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.pk:
            type(self).objects.select_for_update().get(pk=self.pk)
        saves_status = kwargs.get('update_fields') is None or 'status' in kwargs['update_fields']
        now = timezone.now()
        if saves_status and self.status == self.Status.OPEN and not self.opened_at:
            self.opened_at = now
        if saves_status and self.status == self.Status.INTAKE_CLOSED and not self.intake_closed_at:
            self.intake_closed_at = now
        if saves_status and self.status == self.Status.COMPLETED and not self.completed_at:
            self.completed_at = now
        if saves_status and kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {
                'opened_at', 'intake_closed_at', 'completed_at',
            }
        self.full_clean()
        super().save(*args, **kwargs)
        if saves_status and self.status != self.Status.OPEN:
            self.vacancies.filter(status='open').update(status='closed', updated_at=now)


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
    cohort = models.ForeignKey(
        RecruitmentCohort, on_delete=models.PROTECT, null=True, blank=True,
        related_name='vacancies', help_text='Current intake cohort. Leave blank for unbatched recruitment.',
    )
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
        return (
            self.is_active and self.status == 'open'
            and (
                self.cohort_id is None
                or (self.cohort_id is not None and self.cohort.status == RecruitmentCohort.Status.OPEN)
            )
        )

    def clean(self):
        if (
            self.status == 'open' and self.cohort_id
            and self.cohort.status != RecruitmentCohort.Status.OPEN
        ):
            raise ValidationError({'cohort': 'Choose an open cohort or leave blank for unbatched recruitment.'})
        if self.pk and self.applications.exists():
            original = type(self).objects.get(pk=self.pk)
            protected = ('slug', 'title', 'team', 'engagement_type')
            if any(getattr(self, field) != getattr(original, field) for field in protected):
                raise ValidationError('Role identity cannot change after applications exist.')

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.cohort_id:
            self.cohort = RecruitmentCohort.objects.select_for_update().get(pk=self.cohort_id)
        if self.pk:
            type(self).objects.select_for_update().get(pk=self.pk)
        self.clean()
        super().save(*args, **kwargs)

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
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        REVIEWING = "reviewing", "Reviewing"
        SHORTLISTED = "shortlisted", "Shortlisted"
        OFFERED = "offered", "Offered"
        OFFER_ACCEPTED = "offer_accepted", "Offer accepted"
        OFFER_DECLINED = "offer_declined", "Offer declined"
        AGREEMENT_PENDING = "agreement_pending", "Awaiting agreement signature"
        AGREEMENT_SIGNED = "agreement_signed", "Agreement signed"
        AGREEMENT_DECLINED = "agreement_declined", "Agreement declined"
        APPOINTED = "appointed", "Appointed"
        ONBOARDING = "onboarding", "Onboarding"
        ONBOARDING_FAILED = "onboarding_failed", "Onboarding not completed"
        ACTIVE = "active", "Active"
        NOT_SELECTED = "not_selected", "Not selected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        CLOSED = "closed", "Closed"

    class RejectionEmailStatuses(models.TextChoices):
        NOT_SENT = 'not_sent', 'Not sent'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    INTERVIEW_EMAIL_STATUS_CHOICES = RejectionEmailStatuses.choices
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='applications')
    cohort = models.ForeignKey(
        RecruitmentCohort, on_delete=models.PROTECT, null=True, blank=True,
        related_name='applications',
    )
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
    status = models.CharField(max_length=20, choices=Status.choices, default='received')
    agreement_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    agreement_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name='agreements_verified_for_appointment',
    )
    appointed_at = models.DateTimeField(null=True, blank=True, editable=False)
    appointed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name='candidates_appointed',
    )
    onboarding_completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    onboarding_completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name='applications_onboarding_completed',
    )
    acknowledgement_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    slack_notified_at = models.DateTimeField(null=True, blank=True, editable=False)
    newsletter_opt_in = models.BooleanField(default=False)
    newsletter_subscribed_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    notification_error = models.TextField(blank=True, editable=False)
    rejection_email_status = models.CharField(
        max_length=20,
        choices=RejectionEmailStatuses.choices,
        default='not_sent',
        editable=False,
    )
    rejection_email_batch_key = models.UUIDField(null=True, editable=False)
    rejection_email_message_id = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
    )
    rejection_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    rejection_email_sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='rejection_emails_sent',
    )
    shortlisted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='candidates_shortlisted',
    )
    shortlisted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    rejection_email_error = models.TextField(blank=True, editable=False)
    interview_email_status = models.CharField(
        max_length=20,
        choices=INTERVIEW_EMAIL_STATUS_CHOICES,
        default='not_sent',
        editable=False,
    )
    interview_email_batch_key = models.UUIDField(null=True, editable=False)
    interview_email_message_id = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
    )
    interview_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    interview_email_sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='interview_invitations_sent',
    )
    interview_email_error = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        permissions = (
            ('send_volunteer_offer', 'Can prepare and send volunteer offers'),
            ('send_onboarding_email', 'Can send volunteer onboarding emails'),
            ('send_rejection_email', 'Can send volunteer rejection emails'),
            ('send_interview_invitation', 'Can send volunteer interview invitations'),
        )
        constraints = [
            models.UniqueConstraint(fields=('vacancy', 'cohort', 'applicant'),
                                    name='unique_cohort_vacancy_applicant'),
            models.UniqueConstraint(fields=('vacancy', 'applicant'),
                                    condition=models.Q(cohort__isnull=True),
                                    name='unique_unbatched_vacancy_applicant'),
            models.UniqueConstraint('vacancy', 'cohort', Lower('email'),
                                    condition=models.Q(cohort__isnull=False),
                                    name='unique_cohort_vacancy_email'),
            models.UniqueConstraint('vacancy', Lower('email'),
                                    condition=models.Q(cohort__isnull=True),
                                    name='unique_unbatched_vacancy_email'),
        ]

    def __str__(self):
        return f'{self.full_name} - {self.vacancy}'

    def save(self, *args, **kwargs):
        if self.status == self.Status.APPOINTED:
            from user.models import Engagement
            if not (
                self.appointed_at and self.appointed_by_id
                and Engagement.objects.filter(source_application_id=self.pk).exists()
            ):
                raise ValidationError('Appointment requires a linked team engagement and recorded actor.')
        super().save(*args, **kwargs)


class PrivateDocumentDeletion(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'

    storage_name = models.CharField(max_length=1000, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self):
        return f'{self.get_status_display()}: {self.storage_name}'


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


class VolunteerOnboarding(models.Model):
    DELIVERY_STATUS_CHOICES = (
        ('draft', 'Not sent'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    )

    application = models.OneToOneField(
        VacancyApplication,
        on_delete=models.CASCADE,
        related_name='volunteer_onboarding',
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='draft',
    )
    delivery_key = models.UUIDField(default=uuid4, unique=True, editable=False)
    send_count = models.PositiveIntegerField(default=0, editable=False)
    first_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='volunteer_onboarding_emails_sent',
    )
    brevo_message_id = models.CharField(max_length=255, blank=True, editable=False)
    delivery_error = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-last_sent_at', '-created_at')

    def __str__(self):
        return f'Onboarding email for {self.application.full_name}'
