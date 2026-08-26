from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0016_restrict_writer_media_change'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='feature_img',
            field=models.ImageField(
                blank=True,
                help_text=(
                    'Legacy local feature image. New editorial images use managed OEF media.'
                ),
                upload_to='article_feature_img',
            ),
        ),
    ]
