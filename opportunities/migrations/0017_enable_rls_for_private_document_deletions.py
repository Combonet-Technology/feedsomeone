from django.db import migrations

TABLES = ('opportunities_privatedocumentdeletion',)


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
    dependencies = [('opportunities', '0016_private_document_deletion')]
    operations = [migrations.RunPython(enable_rls, reverse_code=disable_rls)]
