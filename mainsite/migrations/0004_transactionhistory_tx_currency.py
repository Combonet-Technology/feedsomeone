# Generated by Django 3.2 on 2023-09-21 11:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mainsite', '0003_auto_20230918_2015'),
    ]

    operations = [
        migrations.AddField(
            model_name='transactionhistory',
            name='tx_currency',
            field=models.CharField(default='naira', max_length=100),
            preserve_default=False,
        ),
    ]