import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def add_rejection_permission_to_recruitment_managers(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    content_type, _ = ContentType.objects.get_or_create(
        app_label='opportunities',
        model='vacancyapplication',
    )
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename='send_rejection_email',
        defaults={'name': 'Can send volunteer rejection emails'},
    )
    group, _ = Group.objects.get_or_create(name='Recruitment Manager')
    group.permissions.add(permission)


def remove_rejection_permission_from_recruitment_managers(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    group = Group.objects.filter(name='Recruitment Manager').first()
    permission = Permission.objects.filter(
        content_type__app_label='opportunities',
        codename='send_rejection_email',
    ).first()
    if group and permission:
        group.permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('opportunities', '0012_volunteer_onboarding'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='vacancyapplication',
            options={
                'ordering': ('-created_at',),
                'permissions': (
                    ('send_volunteer_offer', 'Can prepare and send volunteer offers'),
                    ('send_onboarding_email', 'Can send volunteer onboarding emails'),
                    ('send_rejection_email', 'Can send volunteer rejection emails'),
                ),
            },
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='rejection_email_batch_key',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='rejection_email_error',
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='rejection_email_message_id',
            field=models.CharField(blank=True, editable=False, max_length=255),
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='rejection_email_sent_at',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='rejection_email_sent_by',
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rejection_emails_sent',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='rejection_email_status',
            field=models.CharField(
                choices=[
                    ('not_sent', 'Not sent'),
                    ('sending', 'Sending'),
                    ('sent', 'Sent'),
                    ('failed', 'Failed'),
                ],
                default='not_sent',
                editable=False,
                max_length=20,
            ),
        ),
        migrations.RunPython(
            add_rejection_permission_to_recruitment_managers,
            reverse_code=remove_rejection_permission_from_recruitment_managers,
        ),
    ]
