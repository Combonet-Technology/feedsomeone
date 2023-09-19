import uuid
from dataclasses import dataclass
from typing import Optional

from django.db import models
from django.utils import timezone

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
    tr_id = models.CharField(max_length=100, null=True, blank=True)
    tx_status = models.CharField(max_length=100)
    tx_ref = models.CharField(max_length=255)
    subscription = models.ForeignKey('PaymentSubscription', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='tx_history')
    amount = models.FloatField(default=0.0)
    date_created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.tx_status}-{self.tr_id}'

    class Meta:
        verbose_name_plural = 'Transactions'


class PaymentSubscription(models.Model):
    plan_id = models.CharField(max_length=100, null=True, blank=True)
    plan_status = models.CharField(max_length=100)
    plan_name = models.CharField(max_length=100, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)


class GalleryImage(models.Model):
    image = models.ImageField(upload_to='event_pics')
    image_title = models.CharField(max_length=100, default="Event Excerpts")
    date_posted = models.DateTimeField(default=timezone.now)
    event = models.ForeignKey(Events, related_name='event_image', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.image_title

    class Meta:
        verbose_name_plural = 'Gallery Images'


@dataclass
class RequestCustomerPayment:
    full_name: Optional[str]
    email: str
    phone_number: Optional[str]
    address: Optional[str]

    def validate(self):
        if not self.email:
            raise Exception("Email cannot be blank")


@dataclass
class SubscriptionFilter:
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    page: Optional[int] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    interval: Optional[str] = None
    status: Optional[str] = None
