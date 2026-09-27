import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0014_defer_legacy_engagement_reconciliation'),
    ]

    operations = [
        migrations.AddField(
            model_name='engagement',
            name='access_review_required',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='BackendAccessInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed')], default='pending', max_length=12)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('sending_started_at', models.DateTimeField(blank=True, null=True)),
                ('message_id', models.CharField(blank=True, max_length=255)),
                ('error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('team_member', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='backend_invitations', to='user.teammember')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='backend_invitations', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at',)},
        ),
    ]
