# Generated by Django 3.2 on 2023-05-22 03:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0007_auto_20230519_1245'),
    ]

    operations = [
        migrations.CreateModel(
            name='Table',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('random', models.CharField(blank=True, default='Website', max_length=50, null=True)),
            ],
        ),
    ]