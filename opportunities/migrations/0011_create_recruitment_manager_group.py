from django.db import migrations

GROUP_NAME = 'Recruitment Manager'
PERMISSIONS = (
    ('vacancy', 'view_vacancy', 'Can view vacancy'),
    ('vacancyapplication', 'view_vacancyapplication', 'Can view vacancy application'),
    ('vacancyapplication', 'change_vacancyapplication', 'Can change vacancy application'),
    (
        'vacancyapplication',
        'send_volunteer_offer',
        'Can prepare and send volunteer offers',
    ),
    ('volunteeroffer', 'view_volunteeroffer', 'Can view volunteer offer'),
)


def create_recruitment_manager_group(apps, schema_editor):
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


def remove_recruitment_manager_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('opportunities', '0010_alter_vacancyapplication_options_and_more'),
    ]

    operations = [
        migrations.RunPython(
            create_recruitment_manager_group,
            reverse_code=remove_recruitment_manager_group,
        ),
    ]
