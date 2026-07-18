from django.conf import settings
from django.db import models
from django.urls import reverse


class Vacancy(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('filled', 'Filled'),
        ('closed', 'Closed'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)
    summary = models.CharField(max_length=500)
    description = models.TextField()
    expectations = models.TextField()
    responsibilities = models.TextField()
    benefits = models.TextField()
    who_we_are_looking_for = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    positions_available = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
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
    cv = models.FileField(upload_to='vacancy_applications/cv/')
    cover_letter = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
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
