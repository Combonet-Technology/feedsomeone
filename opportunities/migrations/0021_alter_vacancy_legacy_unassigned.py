from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('opportunities', '0020_vacancy_legacy_unassigned'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vacancy',
            name='legacy_unassigned',
            field=models.BooleanField(
                default=False,
                editable=False,
                help_text='Historical opening created before cohort assignment was required.',
            ),
        ),
    ]
