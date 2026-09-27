import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('opportunities', '0021_alter_vacancy_legacy_unassigned'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vacancyapplication',
            name='status',
            field=models.CharField(
                choices=[
                    ('received', 'Received'), ('reviewing', 'Reviewing'),
                    ('shortlisted', 'Shortlisted'), ('offered', 'Offered'),
                    ('offer_accepted', 'Offer accepted'),
                    ('offer_declined', 'Offer declined'),
                    ('agreement_pending', 'Awaiting agreement signature'),
                    ('agreement_signed', 'Agreement signed'),
                    ('agreement_declined', 'Agreement declined'),
                    ('appointed', 'Appointed — onboarding complete'),
                    ('onboarding', 'Onboarding'),
                    ('onboarding_failed', 'Onboarding not completed'),
                    ('active', 'Active'), ('not_selected', 'Not selected'),
                    ('withdrawn', 'Withdrawn'), ('closed', 'Closed'),
                ], default='received', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='onboarding_completed_at',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='vacancyapplication',
            name='onboarding_completed_by',
            field=models.ForeignKey(
                blank=True, editable=False, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='applications_onboarding_completed',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
