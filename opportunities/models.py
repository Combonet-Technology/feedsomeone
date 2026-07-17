from django.conf import settings
from django.db import models
from django.urls import reverse


class Vacancy(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)
    summary = models.CharField(max_length=500)
    description = models.TextField()
    expectations = models.TextField()
    responsibilities = models.TextField()
    benefits = models.TextField()
    who_we_are_looking_for = models.TextField()
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


class VacancyApplication(models.Model):
    STATUS_CHOICES = (
        ('received', 'Received'),
        ('reviewing', 'Reviewing'),
        ('shortlisted', 'Shortlisted'),
        ('closed', 'Closed'),
    )
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='vacancy_applications')
    cv = models.FileField(upload_to='vacancy_applications/cv/')
    cover_letter = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=('vacancy', 'applicant'), name='unique_vacancy_applicant'),
        ]

    def __str__(self):
        return f'{self.applicant} - {self.vacancy}'
