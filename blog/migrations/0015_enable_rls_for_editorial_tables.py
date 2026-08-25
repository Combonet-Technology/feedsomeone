from django.db import migrations

TABLES = (
    'blog_mediaasset',
    'blog_articlerevision',
    'blog_articlerevision_media_assets',
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
    dependencies = [('blog', '0014_article_feature_crop')]
    operations = [migrations.RunPython(enable_rls, reverse_code=disable_rls)]
