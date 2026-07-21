from django.db import migrations

TABLES = (
    'opportunities_vacancy',
    'opportunities_vacancyapplication',
)


def set_rls(schema_editor, enabled):
    if schema_editor.connection.vendor != 'postgresql':
        return

    action = 'ENABLE' if enabled else 'DISABLE'
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(
                f'ALTER TABLE public.{table} {action} ROW LEVEL SECURITY;'
            )


def enable_rls(apps, schema_editor):
    set_rls(schema_editor, enabled=True)


def disable_rls(apps, schema_editor):
    set_rls(schema_editor, enabled=False)


class Migration(migrations.Migration):
    dependencies = [
        ('opportunities', '0008_vacancyapplication_newsletter_opt_in_and_more'),
    ]

    operations = [
        migrations.RunPython(
            enable_rls,
            reverse_code=disable_rls,
        ),
    ]
