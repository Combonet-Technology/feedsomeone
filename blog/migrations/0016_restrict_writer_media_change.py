from django.db import migrations

WRITER_GROUP = 'OEF Writers'


def remove_writer_media_change(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    writer = Group.objects.filter(name=WRITER_GROUP).first()
    permission = Permission.objects.filter(
        content_type__app_label='blog',
        content_type__model='mediaasset',
        codename='change_mediaasset',
    ).first()
    if writer and permission:
        writer.permissions.remove(permission)


def restore_writer_media_change(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    writer = Group.objects.filter(name=WRITER_GROUP).first()
    permission = Permission.objects.filter(
        content_type__app_label='blog',
        content_type__model='mediaasset',
        codename='change_mediaasset',
    ).first()
    if writer and permission:
        writer.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ('blog', '0015_enable_rls_for_editorial_tables'),
    ]

    operations = [
        migrations.RunPython(
            remove_writer_media_change,
            restore_writer_media_change,
        ),
    ]
