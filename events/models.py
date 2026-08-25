from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.urls import reverse

User = get_user_model()


def generate_event_gallery_tag():
    return f'oef-event-{uuid4().hex}'


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
    date_updated = models.DateTimeField("date_updated", null=True, blank=True)
    event_author = models.ForeignKey(User, related_name='event_author', on_delete=models.SET_NULL, null=True)
    gallery_tag = models.SlugField(
        max_length=96,
        unique=True,
        default=generate_event_gallery_tag,
        help_text='Stable Cloudinary tag used to attach images to this event.',
    )
    gallery_is_public = models.BooleanField(
        default=False,
        help_text='Show database-approved gallery images on the public website.',
    )

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse(
            'event-details',
            kwargs={'pk': self.pk, 'slug': self.event_slug},
        )

    class Meta:
        verbose_name_plural = 'Events'
        db_table = 'mainsite_events'


class EventGallery(Events):
    """Admin-facing gallery catalogue backed by each event's Cloudinary tag."""

    class Meta:
        proxy = True
        verbose_name = 'Event gallery'
        verbose_name_plural = 'Event galleries'


class EventGalleryImage(models.Model):
    """Database index for an event image whose binary is stored in Cloudinary."""

    event = models.ForeignKey(
        Events, on_delete=models.CASCADE, related_name='gallery_images',
    )
    asset_id = models.CharField(max_length=255, blank=True)
    public_id = models.CharField(max_length=255, unique=True)
    secure_url = models.URLField(max_length=1000)
    original_filename = models.CharField(max_length=255, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    tags = models.JSONField(default=list, blank=True)
    is_public = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='uploaded_event_gallery_images',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        verbose_name = 'Gallery image'
        verbose_name_plural = 'Gallery images'

    def __str__(self):
        return self.original_filename or self.public_id


class GalleryUploadBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='gallery_upload_batches',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.pk)


def gallery_staging_path(instance, filename):
    return f'{instance.batch_id}/{uuid4().hex}-{filename}'


class GalleryUploadItem(models.Model):
    from events.storage import gallery_staging_storage

    batch = models.ForeignKey(
        GalleryUploadBatch, on_delete=models.CASCADE, related_name='items',
    )
    staged_file = models.FileField(
        upload_to=gallery_staging_path, storage=gallery_staging_storage,
    )
    original_filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


@receiver(pre_delete, sender=GalleryUploadItem)
def delete_staged_gallery_file(sender, instance, **kwargs):
    if instance.staged_file and instance.staged_file.name:
        instance.staged_file.storage.delete(instance.staged_file.name)


class Sponsors(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)


class EventSponsors(models.Model):
    event = models.ManyToManyField(Events, blank=True)
    sponsor = models.ManyToManyField(Sponsors, blank=True)
