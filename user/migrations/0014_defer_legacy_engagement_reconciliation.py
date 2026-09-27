from django.db import migrations


class Migration(migrations.Migration):
    """Reserve the schema step; historical people need approved reconciliation.

    Do not infer engagement, onboarding or end states from legacy TeamMember
    fields. A read-only reconciliation report and founder-approved mapping must
    precede any production backfill.
    """

    dependencies = [
        ('user', '0013_alter_teammember_options_teammember_full_name_and_more'),
    ]

    operations = []
