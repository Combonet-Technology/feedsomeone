from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0003_event_gallery_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventGallery',
            fields=[],
            options={
                'verbose_name': 'Event gallery',
                'verbose_name_plural': 'Event galleries',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('events.events',),
        ),
    ]
