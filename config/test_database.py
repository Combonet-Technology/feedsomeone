"""Guard the real PostgreSQL test backend and cross-connection row locking."""

from uuid import uuid4

from django.contrib.auth.models import Group
from django.db import OperationalError, connection, transaction
from django.test import SimpleTestCase


class PostgreSQLTestDatabaseTests(SimpleTestCase):
    databases = {'default'}

    def test_test_database_is_isolated_and_row_locks_are_enforced(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        original_groups = set(Group.objects.values_list('pk', flat=True))
        group = Group.objects.create(name=f'row-lock-probe-{uuid4()}')
        probe = connection.copy()
        try:
            with transaction.atomic():
                Group.objects.select_for_update().get(pk=group.pk)
                with self.assertRaises(OperationalError) as caught:
                    with probe.cursor() as cursor:
                        cursor.execute(
                            'SELECT id FROM auth_group WHERE id = %s FOR UPDATE NOWAIT',
                            [group.pk],
                        )
                self.assertEqual(caught.exception.__cause__.diag.sqlstate, '55P03')
            with probe.cursor() as cursor:
                cursor.execute(
                    'SELECT id FROM auth_group WHERE id = %s FOR UPDATE NOWAIT', [group.pk],
                )
                self.assertEqual(cursor.fetchone()[0], group.pk)
        finally:
            probe.close()
            group.delete()
        self.assertEqual(set(Group.objects.values_list('pk', flat=True)), original_groups)
