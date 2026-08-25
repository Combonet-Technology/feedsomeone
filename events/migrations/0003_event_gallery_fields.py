from uuid import uuid4

from django.db import migrations, models

import events.models


def temporary_gallery_tag():
    return f'oef-event-{uuid4().hex}'


def preserve_historical_tags(apps, schema_editor):
    Event = apps.get_model('events', 'Events')
    for event in Event.objects.all().iterator():
        candidates = f'{event.event_slug or ""} {event.title or ""}'.lower()
        if 'feed-someone-1.0' in candidates or 'feed-someone-1-0' in candidates:
            event.gallery_tag = 'feed-someone-1.0'
            event.gallery_is_public = True
        elif 'feed-someone-2.0' in candidates or 'feed-someone-2-0' in candidates:
            event.gallery_tag = 'feed-someone-2.0'
            event.gallery_is_public = True
        else:
            event.gallery_tag = temporary_gallery_tag()
        event.save(update_fields=('gallery_tag', 'gallery_is_public'))


class Migration(migrations.Migration):
    dependencies = [('events', '0002_initial')]

    operations = [
        migrations.AddField(
            model_name='events',
            name='gallery_tag',
            field=models.CharField(
                max_length=96,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='events',
            name='gallery_is_public',
            field=models.BooleanField(
                default=False,
                help_text='Show publication-approved gallery images on the public website.',
            ),
        ),
        migrations.RunPython(preserve_historical_tags, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='events',
            name='gallery_tag',
            field=models.SlugField(
                default=events.models.generate_event_gallery_tag,
                help_text='Stable Cloudinary tag used to attach images to this event.',
                max_length=96,
                unique=True,
            ),
        ),
    ]
