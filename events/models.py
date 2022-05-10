from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


# Create your models here.
class Volunteer(models.Model):
    user = models.ManyToManyField(User, blank=True, related_name='related_user')
    event = models.ForeignKey("Event", on_delete=models.CASCADE, null=True)
    approved = models.BooleanField(null=True, blank=True, default=False)
    instr_sent = models.BooleanField(null=True, blank=True, default=False)
    active = models.BooleanField(null=True, blank=True, default=False)


class Event(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)
    date = models.DateField()
    description = models.TextField(null=True, blank=True)
    location = models.TextField(null=True, blank=True)
    max_volunteer_needed = models.IntegerField()
    budget = models.FloatField()


class Sponsors(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)


class EventSponsors(models.Model):
    event = models.ManyToManyField(Event, blank=True)
    sponsor = models.ManyToManyField(Sponsors, blank=True)
