from django.urls import reverse
from django.utils import timezone
from django.db import models

# TODO reassign deleted posts and images to admin
#  USING https://medium.com/@inem.patrick/django-database-integrity-foreignkey-on-delete-option-db7d160762e4
from events.models import Events
from user.models import UserProfile


class TransactionHistory(models.Model):
    status = models.CharField(max_length=100)
    tx_ref = models.CharField(max_length=100)
    tr_id = models.IntegerField()
    amount = models.FloatField(default=0.0)
    date_created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.status}-{self.tr_id}'

    class Meta:
        verbose_name_plural = 'Transactions'


class GalleryImage(models.Model):
    image = models.ImageField(upload_to='event_pics')
    image_title = models.CharField(max_length=100, default="Event Excerpts")
    date_posted = models.DateTimeField(default=timezone.now)
    event = models.ForeignKey(Events, related_name='event_image', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.image_title

    class Meta:
        verbose_name_plural = 'Gallery Images'


