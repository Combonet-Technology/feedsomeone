from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('opportunities', '0024_application_cohort_intake'),
    ]

    operations = [
        migrations.RemoveField(model_name='vacancy', name='legacy_unassigned'),
    ]
