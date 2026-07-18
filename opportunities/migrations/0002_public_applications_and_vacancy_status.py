import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_application_identity(apps, schema_editor):
    VacancyApplication = apps.get_model('opportunities', 'VacancyApplication')
    for application in VacancyApplication.objects.select_related('applicant'):
        applicant = application.applicant
        application.full_name = applicant.get_full_name() or applicant.email
        application.email = applicant.email.lower()
        application.save(update_fields=('full_name', 'email'))


class Migration(migrations.Migration):
    dependencies = [
        ('opportunities', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='positions_available',
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='vacancy',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('open', 'Open'),
                    ('filled', 'Filled'),
                    ('closed', 'Closed'),
                ],
                default='draft',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='email',
            field=models.EmailField(default='', max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='full_name',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='phone',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AlterField(
            model_name='vacancyapplication',
            name='applicant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vacancy_applications',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            populate_application_identity,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='vacancyapplication',
            constraint=models.UniqueConstraint(
                fields=('vacancy', 'email'),
                name='unique_vacancy_email',
            ),
        ),
    ]
