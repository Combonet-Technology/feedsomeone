# Generated by Django 3.2 on 2023-05-11 12:29

import taggit.managers
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        # ('taggit', '0004_auto_20230501_1835'),
        ('blog', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='tags',
            field=taggit.managers.TaggableManager(help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags'),
        ),
    ]
