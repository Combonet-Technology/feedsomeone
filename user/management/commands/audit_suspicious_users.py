import csv
from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone


class Command(BaseCommand):
    help = 'Read-only audit of old, inactive, non-privileged accounts with no donation record.'

    def add_arguments(self, parser):
        parser.add_argument('--before', required=True, help='Cutoff date in YYYY-MM-DD format.')
        parser.add_argument('--output', help='Optional CSV output path. No users are changed or deleted.')

    def handle(self, *args, **options):
        try:
            cutoff_date = datetime.strptime(options['before'], '%Y-%m-%d').date()
        except ValueError as exc:
            raise CommandError('--before must use YYYY-MM-DD format.') from exc

        cutoff = timezone.make_aware(datetime.combine(cutoff_date, time.min))
        User = get_user_model()
        candidates = (
            User.objects.filter(
                is_active=False,
                is_staff=False,
                is_superuser=False,
                date_joined__lt=cutoff,
                donor__isnull=True,
            )
            .filter(Q(last_login__isnull=True) | Q(last_login__lt=cutoff))
            .select_related('volunteer')
            .order_by('date_joined')
        )

        rows = []
        for user in candidates.iterator():
            volunteer = getattr(user, 'volunteer', None)
            rows.append({
                'id': str(user.pk),
                'email': user.email or '',
                'username': user.username or '',
                'date_joined': user.date_joined.isoformat() if user.date_joined else '',
                'last_login': user.last_login.isoformat() if user.last_login else '',
                'has_volunteer_profile': bool(volunteer),
                'volunteer_verified': bool(volunteer and volunteer.is_verified),
                'reason': 'inactive, old, no recent login, no donation record',
            })

        self.stdout.write(f'Candidates: {len(rows)}')
        self.stdout.write('Mode: READ ONLY (no accounts changed)')

        if options.get('output'):
            fieldnames = list(rows[0]) if rows else [
                'id', 'email', 'username', 'date_joined', 'last_login',
                'has_volunteer_profile', 'volunteer_verified', 'reason',
            ]
            with open(options['output'], 'w', newline='', encoding='utf-8') as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            self.stdout.write(self.style.SUCCESS(f"Report written to {options['output']}"))
