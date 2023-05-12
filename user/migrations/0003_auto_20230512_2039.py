# Generated by Django 3.2 on 2023-05-12 19:39

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import user.enums


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0002_auto_20230512_1820'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='donor',
            name='userprofile_ptr',
        ),
        migrations.RemoveField(
            model_name='volunteer',
            name='country',
        ),
        migrations.RemoveField(
            model_name='volunteer',
            name='state',
        ),
        migrations.RemoveField(
            model_name='volunteer',
            name='userprofile_ptr',
        ),
        migrations.AddField(
            model_name='donor',
            name='id',
            field=models.BigAutoField(auto_created=True, default=django.utils.timezone.now, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='donor',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='donor', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='volunteer',
            name='ethnicity',
            field=models.CharField(blank=True, choices=[(user.enums.EthnicityEnum['HAUSA'], 'HAUSA'), (user.enums.EthnicityEnum['IGBO'], 'IGBO'), (user.enums.EthnicityEnum['YORUBA'], 'YORUBA'), (user.enums.EthnicityEnum['FULANI'], 'FULANI'), (user.enums.EthnicityEnum['IBIBIO'], 'IBIBIO'), (user.enums.EthnicityEnum['EDO'], 'EDO'), (user.enums.EthnicityEnum['IJAW'], 'IJAW'), (user.enums.EthnicityEnum['ITSEKIRI'], 'ITSEKIRI'), (user.enums.EthnicityEnum['BENIN'], 'BENIN'), (user.enums.EthnicityEnum['IGALA'], 'IGALA'), (user.enums.EthnicityEnum['IDOMA'], 'IDOMA'), (user.enums.EthnicityEnum['KANURI'], 'KANURI'), (user.enums.EthnicityEnum['EFIK'], 'EFIK'), (user.enums.EthnicityEnum['BWARI'], 'BWARI'), (user.enums.EthnicityEnum['TIV'], 'TIV'), (user.enums.EthnicityEnum['BIROM'], 'BIROM'), (user.enums.EthnicityEnum['ANGERS'], 'ANGERS'), (user.enums.EthnicityEnum['IDOMINA'], 'IDOMINA'), (user.enums.EthnicityEnum['EBIRA'], 'EBIRA')], max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='volunteer',
            name='id',
            field=models.BigAutoField(auto_created=True, default=django.utils.timezone.now, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='volunteer',
            name='profession',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='volunteer',
            name='religion',
            field=models.CharField(blank=True, choices=[(user.enums.ReligionEnum['CHRISTIANITY'], 'CHRISTIANITY'), (user.enums.ReligionEnum['ISLAM'], 'ISLAM'), (user.enums.ReligionEnum['TRADITIONALIST'], 'TRADITIONALIST'), (user.enums.ReligionEnum['OTHERS'], 'OTHERS')], max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='volunteer',
            name='state_of_residence',
            field=models.CharField(blank=True, choices=[(user.enums.StateEnum['ABIA'], 'ABIA'), (user.enums.StateEnum['ADAMAWA'], 'ADAMAWA'), (user.enums.StateEnum['AKWA'], 'AKWA'), (user.enums.StateEnum['IBOM'], 'IBOM'), (user.enums.StateEnum['ANAMBRA'], 'ANAMBRA'), (user.enums.StateEnum['BAUCHI'], 'BAUCHI'), (user.enums.StateEnum['BAYELSA'], 'BAYELSA'), (user.enums.StateEnum['BENUE'], 'BENUE'), (user.enums.StateEnum['BORNO'], 'BORNO'), (user.enums.StateEnum['CROSSRIVER'], 'CROSS RIVER'), (user.enums.StateEnum['DELTA'], 'DELTA'), (user.enums.StateEnum['EBONYI'], 'EBONYI'), (user.enums.StateEnum['EDO'], 'EDO'), (user.enums.StateEnum['EKITI'], 'EKITI'), (user.enums.StateEnum['ENUGU'], 'ENUGU'), (user.enums.StateEnum['GOMBE'], 'GOMBE'), (user.enums.StateEnum['IMO'], 'IMO'), (user.enums.StateEnum['JIGAWA'], 'JIGAWA'), (user.enums.StateEnum['KADUNA'], 'KADUNA'), (user.enums.StateEnum['KANO'], 'KANO'), (user.enums.StateEnum['KATSINA'], 'KATSINA'), (user.enums.StateEnum['KEBBI'], 'KEBBI'), (user.enums.StateEnum['KOGI'], 'KOGI'), (user.enums.StateEnum['KWARA'], 'KWARA'), (user.enums.StateEnum['LAGOS'], 'LAGOS'), (user.enums.StateEnum['NASARAWA'], 'NASARAWA'), (user.enums.StateEnum['NIGER'], 'NIGER'), (user.enums.StateEnum['OGUN'], 'OGUN'), (user.enums.StateEnum['ONDO'], 'ONDO'), (user.enums.StateEnum['OSUN'], 'OSUN'), (user.enums.StateEnum['OYO'], 'OYO'), (user.enums.StateEnum['PLATEAU'], 'PLATEAU'), (user.enums.StateEnum['RIVERS'], 'RIVERS'), (user.enums.StateEnum['SOKOTO'], 'SOKOTO'), (user.enums.StateEnum['TARABA'], 'TARABA'), (user.enums.StateEnum['YOBE'], 'YOBE'), (user.enums.StateEnum['ZAMFARA'], 'ZAMFARA'), (user.enums.StateEnum['FCT'], 'FCT-ABUJA')], max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='volunteer',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='volunteer', to=settings.AUTH_USER_MODEL),
        ),
    ]
