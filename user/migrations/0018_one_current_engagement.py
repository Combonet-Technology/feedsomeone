from django.db import migrations, models
from django.db.models import Count


def check_existing_engagements(apps, schema_editor):
    engagement = apps.get_model('user', 'Engagement')
    rows = engagement.objects.using(schema_editor.connection.alias)
    duplicates = list(
        rows.filter(status__in=('onboarding', 'active')).values('team_member_id')
        .annotate(current_count=Count('pk')).filter(current_count__gt=1)
    )
    invalid_dates = list(rows.filter(end_date__lt=models.F('start_date')).values_list('pk', flat=True))
    if duplicates or invalid_dates:
        raise RuntimeError(
            f'Reconcile engagements before migrating: current duplicates={duplicates}; '
            f'invalid date record IDs={invalid_dates}. No records were changed.'
        )


class Migration(migrations.Migration):
    dependencies = [('user', '0017_alter_teammember_role_title')]

    operations = [
        migrations.RunPython(check_existing_engagements, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='engagement',
            constraint=models.UniqueConstraint(
                fields=('team_member',), condition=models.Q(status__in=('onboarding', 'active')),
                name='one_current_engagement_per_member',
            ),
        ),
        migrations.AddConstraint(
            model_name='engagement',
            constraint=models.CheckConstraint(
                condition=models.Q(start_date__isnull=True) | models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=models.F('start_date')),
                name='engagement_dates_in_order',
            ),
        ),
    ]
