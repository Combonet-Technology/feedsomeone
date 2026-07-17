import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='Vacancy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=255, unique=True)),
                ('summary', models.CharField(max_length=500)),
                ('description', models.TextField()),
                ('expectations', models.TextField()),
                ('responsibilities', models.TextField()),
                ('benefits', models.TextField()),
                ('who_we_are_looking_for', models.TextField()),
                ('is_active', models.BooleanField(default=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ('-published_at', '-created_at')},
        ),
        migrations.CreateModel(
            name='VacancyApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cv', models.FileField(upload_to='vacancy_applications/cv/')),
                ('cover_letter', models.TextField()),
                ('status', models.CharField(choices=[('received', 'Received'), ('reviewing', 'Reviewing'), ('shortlisted', 'Shortlisted'), ('closed', 'Closed')], default='received', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('applicant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vacancy_applications', to=settings.AUTH_USER_MODEL)),
                ('vacancy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='applications', to='opportunities.vacancy')),
            ],
            options={'ordering': ('-created_at',), 'constraints': [models.UniqueConstraint(fields=('vacancy', 'applicant'), name='unique_vacancy_applicant')]},
        ),
    ]
