from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from mainsite.models import Donor


class AuditSuspiciousUsersCommandTests(TestCase):
    def _old_inactive_user(self, email):
        User = get_user_model()
        user = User.objects.create_user(email=email, password='test-password')
        user.is_active = False
        user.save(update_fields=['is_active'])
        User.objects.filter(pk=user.pk).update(date_joined=timezone.now() - timedelta(days=1000))
        user.refresh_from_db()
        return user

    def test_reports_only_inactive_old_users_without_donations(self):
        candidate = self._old_inactive_user('candidate@example.com')
        donor_user = self._old_inactive_user('donor@example.com')
        Donor.objects.create(user=donor_user)
        active_user = self._old_inactive_user('active@example.com')
        active_user.is_active = True
        active_user.save(update_fields=['is_active'])
        output = StringIO()

        call_command('audit_suspicious_users', before=timezone.now().date().isoformat(), stdout=output)

        self.assertIn('Candidates: 1', output.getvalue())
        self.assertTrue(get_user_model().objects.filter(pk=candidate.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=donor_user.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=active_user.pk).exists())
