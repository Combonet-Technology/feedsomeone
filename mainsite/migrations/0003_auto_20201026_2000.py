# Generated by Django 3.1.2 on 2020-10-26 19:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mainsite', '0002_auto_20201026_1957'),
    ]

    operations = [
        migrations.RenameField(
            model_name='galleryimage',
            old_name='events_id',
            new_name='event',
        ),
        migrations.AlterField(
            model_name='galleryimage',
            name='image_title',
            field=models.CharField(default='Event Excerpts', max_length=100),
        ),
    ]
