"""Real PostgreSQL concurrent grants, without flushing migration-seeded groups."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.db import connection, connections
from django.test import SimpleTestCase

from user.access import set_backend_access
from user.models import (BackendAccessChange, BackendAccessInvitation,
                         Engagement, TeamMember, UserProfile)


class AccessConcurrencyTests(SimpleTestCase):
    databases = {'default'}

    def test_parallel_grants_enable_once_and_create_one_invitation(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        suffix = uuid4().hex[:12]
        actor = UserProfile.objects.create_superuser(email=f'a-{suffix}@example.org', password='test')
        account = UserProfile.objects.create_user(email=f'm-{suffix}@oluwafemiebenezerfoundation.org')
        member = TeamMember.objects.create(user=account, full_name='Concurrent test', primary_email=account.email)
        engagement = Engagement.objects.create(team_member=member, role_title='Writer', status='active')
        barrier = Barrier(2)

        def grant():
            try:
                barrier.wait(timeout=10)
                result = set_backend_access(
                    member, UserProfile.objects.get(pk=actor.pk), action='grant',
                    reason='Concurrency test', site_url='https://example.org/',
                )
                return result.changed
            finally:
                connections.close_all()

        try:
            with patch('user.access.send_backend_invitation') as send, ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: grant(), range(2)))
            self.assertEqual(sorted(results), [False, True])
            self.assertEqual(BackendAccessInvitation.objects.filter(team_member=member).count(), 1)
            self.assertEqual(BackendAccessChange.objects.filter(team_member=member).count(), 1)
            send.assert_called_once()
            account.refresh_from_db()
            self.assertTrue(account.is_staff)
        finally:
            BackendAccessInvitation.objects.filter(team_member=member).delete()
            BackendAccessChange.objects.filter(team_member=member).delete()
            engagement.delete()
            member.delete()
            account.delete()
            actor.delete()
