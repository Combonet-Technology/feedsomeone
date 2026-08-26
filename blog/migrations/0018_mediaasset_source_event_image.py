import django.db.models.deletion
from django.db import migrations, models


def link_existing_event_sources(apps, schema_editor):
    MediaAsset = apps.get_model('blog', 'MediaAsset')
    EventGalleryImage = apps.get_model('events', 'EventGalleryImage')
    event_images = EventGalleryImage.objects.filter(
        public_id__in=MediaAsset.objects.values_list('public_id', flat=True),
    ).only('pk', 'public_id')
    for image in event_images.iterator():
        MediaAsset.objects.filter(
            public_id=image.public_id,
            source_event_image__isnull=True,
        ).update(source_event_image_id=image.pk)


class Migration(migrations.Migration):
    dependencies = [
        ('events', '0008_enable_rls_for_gallery_tables'),
        ('blog', '0017_remove_article_feature_image_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='mediaasset',
            name='source_event_image',
            field=models.OneToOneField(
                blank=True,
                help_text='Event-gallery source retained while this image is available to articles.',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='editorial_media_asset',
                to='events.eventgalleryimage',
            ),
        ),
        migrations.RunPython(link_existing_event_sources, migrations.RunPython.noop),
    ]
