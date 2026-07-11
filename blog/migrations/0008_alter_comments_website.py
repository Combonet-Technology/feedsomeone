# Generated manually for comment form reliability.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0007_article_tags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comments',
            name='website',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
