from django.db import migrations


def create_manager_group(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    content_type, _ = ContentType.objects.get_or_create(app_label='user', model='teammember')
    permissions = []
    for codename, name in (
        ('manage_team_access', 'Can manage delegable team backend access'),
        ('manage_team_engagement', 'Can appoint and manage team engagements'),
        ('view_teammember', 'Can view team member'),
        ('add_teammember', 'Can add team member'),
        ('change_teammember', 'Can change team member'),
    ):
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type, codename=codename,
            defaults={'name': name},
        )
        permissions.append(permission)
    engagement_type, _ = ContentType.objects.get_or_create(
        app_label='user', model='engagement',
    )
    for codename, name in (
        ('view_engagement', 'Can view engagement'),
        ('add_engagement', 'Can add engagement'),
        ('change_engagement', 'Can change engagement'),
    ):
        permission, _ = Permission.objects.get_or_create(
            content_type=engagement_type, codename=codename,
            defaults={'name': name},
        )
        permissions.append(permission)
    group, _ = Group.objects.get_or_create(name='OEF Managers')
    group.permissions.set(permissions)


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0015_engagement_access_review_and_invitation'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(create_manager_group, migrations.RunPython.noop),
    ]
