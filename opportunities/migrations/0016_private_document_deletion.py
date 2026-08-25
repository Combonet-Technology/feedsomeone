from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('opportunities', '0015_shortlist_applicants')]
    operations = [
        migrations.CreateModel(
            name='PrivateDocumentDeletion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('storage_name', models.CharField(max_length=1000, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('completed', 'Completed')], default='pending', max_length=16)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'ordering': ('created_at',)},
        ),
    ]
