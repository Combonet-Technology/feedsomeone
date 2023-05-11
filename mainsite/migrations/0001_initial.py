# Generated by Django 3.2 on 2023-05-11 12:28

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TransactionHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(max_length=100)),
                ('tx_ref', models.CharField(max_length=100)),
                ('tr_id', models.IntegerField()),
                ('amount', models.FloatField(default=0.0)),
                ('date_created', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name_plural': 'Transactions',
            },
        ),
        migrations.CreateModel(
            name='GalleryImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='event_pics')),
                ('image_title', models.CharField(default='Event Excerpts', max_length=100)),
                ('date_posted', models.DateTimeField(default=django.utils.timezone.now)),
                ('event', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='event_image', to='events.events')),
            ],
            options={
                'verbose_name_plural': 'Gallery Images',
            },
        ),
    ]