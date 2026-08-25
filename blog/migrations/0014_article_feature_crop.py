from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('blog', '0013_mediaasset_quality_score')]

    operations = [
        migrations.AddField(
            model_name='article',
            name='feature_crop',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Original-image crop coordinates for the 16:9 feature placement.',
            ),
        ),
    ]
