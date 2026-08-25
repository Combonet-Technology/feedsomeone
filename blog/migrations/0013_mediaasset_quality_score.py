from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('blog', '0012_article_feature_media_alter_article_feature_img')]

    operations = [
        migrations.AddField(
            model_name='mediaasset',
            name='quality_score',
            field=models.DecimalField(
                blank=True, decimal_places=3, editable=False,
                help_text='Cloudinary focus-quality score when available.',
                max_digits=4, null=True,
            ),
        ),
    ]
