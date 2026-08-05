import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

GROUP_NAME = 'Volunteer Onboarding'
PERMISSIONS = (
    ('vacancy', 'view_vacancy', 'Can view vacancy'),
    ('vacancyapplication', 'view_vacancyapplication', 'Can view vacancy application'),
    (
        'vacancyapplication',
        'send_onboarding_email',
        'Can send volunteer onboarding emails',
    ),
)


def create_volunteer_onboarding_group(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    permissions = []
    for model, codename, name in PERMISSIONS:
        content_type, _ = ContentType.objects.get_or_create(
            app_label='opportunities',
            model=model,
        )
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={'name': name},
        )
        permissions.append(permission)
    group.permissions.set(permissions)


def remove_volunteer_onboarding_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('opportunities', '0011_create_recruitment_manager_group'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='vacancyapplication',
            options={
                'ordering': ('-created_at',),
                'permissions': (
                    ('send_volunteer_offer', 'Can prepare and send volunteer offers'),
                    ('send_onboarding_email', 'Can send volunteer onboarding emails'),
                ),
            },
        ),
        migrations.CreateModel(
            name='VolunteerOnboarding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delivery_status', models.CharField(choices=[('draft', 'Not sent'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed')], default='draft', max_length=20)),
                ('delivery_key', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('send_count', models.PositiveIntegerField(default=0, editable=False)),
                ('first_sent_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('last_sent_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('brevo_message_id', models.CharField(blank=True, editable=False, max_length=255)),
                ('delivery_error', models.TextField(blank=True, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('application', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='volunteer_onboarding', to='opportunities.vacancyapplication')),
                ('last_sent_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='volunteer_onboarding_emails_sent', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-last_sent_at', '-created_at'),
            },
        ),
        migrations.RunPython(
            create_volunteer_onboarding_group,
            reverse_code=remove_volunteer_onboarding_group,
        ),
    ]
