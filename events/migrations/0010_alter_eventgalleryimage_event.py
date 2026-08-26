import django.db.models.deletion
from django.db import migrations, models

import events.models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0009_eventgalleryimage_deletion_state'),
    ]

    operations = [
        migrations.AlterField(
            model_name='events',
            name='gallery_is_public',
            field=models.BooleanField(
                default=False,
                help_text='Show approved gallery images on the public website.',
            ),
        ),
        migrations.AlterField(
            model_name='events',
            name='gallery_tag',
            field=models.SlugField(
                default=events.models.generate_event_gallery_tag,
                help_text='Stable tag used to organise images for this event.',
                max_length=96,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name='eventgalleryimage',
            name='event',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='gallery_images',
                to='events.events',
            ),
        ),
    ]
