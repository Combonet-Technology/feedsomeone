import uuid

from django.urls import reverse
from django.utils import timezone
from django.db import models

# TODO reassign deleted posts and images to admin
#  USING https://medium.com/@inem.patrick/django-database-integrity-foreignkey-on-delete-option-db7d160762e4
from events.models import Events
from user.models import UserProfile


class Donor(models.Model):
    """users that donates to the Foundation"""
    uuid = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    user = models.OneToOneField(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='donor')


class TransactionHistory(models.Model):
    donor = models.ForeignKey(Donor, on_delete=models.SET_NULL, null=True, blank=True, related_name='donations')
    tx_status = models.CharField(max_length=100)
    tx_ref = models.CharField(max_length=100)
    subscription = models.ForeignKey('PaymentSubscription', on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='tx_history')
    amount = models.FloatField(default=0.0)
    date_created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.tx_status}-{self.tr_id}'

    class Meta:
        verbose_name_plural = 'Transactions'


class PaymentSubscription(models.Model):
    plan_id = models.CharField(null=True, blank=True)
    plan_status = models.CharField(max_length=100)
    plan_name = models.CharField(null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    plan_duration = models.IntegerField()


class GalleryImage(models.Model):
    image = models.ImageField(upload_to='event_pics')
    image_title = models.CharField(max_length=100, default="Event Excerpts")
    date_posted = models.DateTimeField(default=timezone.now)
    event = models.ForeignKey(Events, related_name='event_image', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.image_title

    class Meta:
        verbose_name_plural = 'Gallery Images'
