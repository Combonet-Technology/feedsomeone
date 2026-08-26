from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0008_enable_rls_for_gallery_tables'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventgalleryimage',
            name='deletion_error',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='eventgalleryimage',
            name='deletion_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='eventgalleryimage',
            name='deletion_status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'),
                    ('pending', 'Deletion pending'),
                    ('provider_deleted', 'Deletion confirmed'),
                ],
                db_index=True,
                default='active',
                max_length=24,
            ),
        ),
    ]
