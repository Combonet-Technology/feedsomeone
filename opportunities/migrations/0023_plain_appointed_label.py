from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('opportunities', '0022_application_completion_outcomes'),
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
                    ('appointed', 'Appointed'), ('onboarding', 'Onboarding'),
                    ('onboarding_failed', 'Onboarding not completed'),
                    ('active', 'Active'), ('not_selected', 'Not selected'),
                    ('withdrawn', 'Withdrawn'), ('closed', 'Closed'),
                ],
                default='received', max_length=20,
            ),
        ),
    ]
