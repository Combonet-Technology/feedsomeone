from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


# Create your models here.
class Volunteer(models.Model):
    user = models.ManyToManyField(User, blank=True, related_name='related_user')
    event = models.ForeignKey("Events", on_delete=models.CASCADE, null=True)
    approved = models.BooleanField(null=True, blank=True, default=False)
    instr_sent = models.BooleanField(null=True, blank=True, default=False)
    active = models.BooleanField(null=True, blank=True, default=False)


# class Events(models.Model):
#     event_date = models.DateField(null=True)
#     event_slug = models.SlugField(null=True, unique=False, max_length=150)
#     title = models.CharField(max_length=100)
#     location = models.CharField(max_length=35)
#     time = models.CharField(max_length=35)
#     feature_img = models.ImageField(upload_to='event_feature_img')
#     content = models.TextField()
#     budget = models.FloatField(default=20000000)
#     date_posted = models.DateTimeField(default=timezone.now)
#     event_author = models.ForeignKey(User, related_name='+', on_delete=models.SET_NULL, null=True)
#
#     def __str__(self):
#         return self.title
#
#     def get_absolute_url(self):
#         return reverse('event', kwargs={'slug': self.event_slug})
#
#     class Meta:
#         verbose_name_plural = 'Events'

class Events(models.Model):
    title = models.CharField(max_length=100, null=True, blank=True)
    event_date = models.DateField(null=True)
    description = models.TextField(null=True, blank=True)
    location = models.TextField(null=True, blank=True, max_length=50)
    max_volunteer_needed = models.IntegerField(null=True, blank=True)
    budget = models.FloatField(null=True, blank=True)
    event_slug = models.SlugField(null=True, unique=False, max_length=150)
    feature_img = models.ImageField(upload_to='event_feature_img')
    time = models.CharField(max_length=35)
    content = models.TextField()
    date_posted = models.DateTimeField("date_posted", auto_now_add=True)
    date_updated = models.DateTimeField("date_updated", null=True)
    event_author = models.ForeignKey(User, related_name='event_author', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('event', kwargs={'slug': self.event_slug})

    class Meta:
        verbose_name_plural = 'Events'
        db_table = 'mainsite_events'


class Sponsors(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)


class EventSponsors(models.Model):
    event = models.ManyToManyField(Events, blank=True)
    sponsor = models.ManyToManyField(Sponsors, blank=True)


