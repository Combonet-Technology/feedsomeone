from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from user.access import (preview_backend_access, send_backend_invitation,
                         set_backend_access)
from user.models import (BackendAccessChange, BackendAccessInvitation,
                         Engagement, TeamMember, UserProfile)


class DelegatedAccessTests(TestCase):
    def setUp(self):
        self.owner = UserProfile.objects.create_superuser(
            email='owner@example.org', password='test-password',
        )
        self.writer = Group.objects.get(name='OEF Writers')
        self.reviewer = Group.objects.get(name='OEF Reviewers')
        self.publisher = Group.objects.get(name='OEF Publishers')
        self.member = TeamMember.objects.create(
            full_name='Test Member', primary_email='member@example.org',
            role_title='Content Writer',
        )
        self.engagement = Engagement.objects.create(
            team_member=self.member, role_title='Content Writer',
        )

    def activate_engagement(self):
        self.engagement.status = Engagement.Status.ACTIVE
        self.engagement.onboarding_status = Engagement.OnboardingStatus.COMPLETED
        self.engagement.save(update_fields=('status', 'onboarding_status'))

    def test_active_engagement_required_and_assignment_is_audited(self):
        with self.assertRaises(ValidationError):
            set_backend_access(
                self.member, self.owner, {'OEF Writers'},
                reason='Writing work', site_url='https://example.org/',
            )
        self.engagement.status = Engagement.Status.ACTIVE
        self.engagement.save(update_fields=('status',))
        with self.captureOnCommitCallbacks(execute=False):
            result = set_backend_access(
                self.member, self.owner, {'OEF Writers', 'OEF Reviewers'},
                reason='Editorial assignment', site_url='https://example.org/',
            )
        self.assertTrue(result.changed)
        self.assertEqual(self.engagement.onboarding_status, Engagement.OnboardingStatus.NOT_STARTED)
        self.assertTrue(result.user.is_staff)
        self.assertFalse(result.user.has_usable_password())
        self.assertEqual(
            set(result.user.groups.values_list('name', flat=True)),
            {'OEF Writers', 'OEF Reviewers'},
        )
        self.assertEqual(BackendAccessChange.objects.count(), 1)
        self.assertEqual(result.invitation.status, 'pending')
        self.assertFalse(set_backend_access(
            self.member, self.owner, {'OEF Writers', 'OEF Reviewers'},
            reason='No actual change', site_url='https://example.org/',
        ).changed)

    def test_manager_cannot_modify_self_or_select_protected_group(self):
        manager = UserProfile.objects.create_user(
            email='manager@example.org', password='test-password', is_staff=True,
        )
        manager.user_permissions.add(
            Permission.objects.get(content_type__app_label='user', codename='manage_team_access')
        )
        own_member = TeamMember.objects.create(
            user=manager, full_name='Manager', primary_email=manager.email,
            role_title='Programme Coordinator',
        )
        Engagement.objects.create(
            team_member=own_member, role_title='Programme Coordinator',
            status=Engagement.Status.ACTIVE,
            onboarding_status=Engagement.OnboardingStatus.COMPLETED,
        )
        with self.assertRaises(PermissionDenied):
            preview_backend_access(own_member, manager, {'OEF Writers'})
        with self.assertRaises(ValidationError):
            preview_backend_access(self.member, manager, {'OEF Managers'})

    def test_suspend_removes_staff_capability_without_ending_engagement(self):
        self.activate_engagement()
        with self.captureOnCommitCallbacks(execute=False):
            set_backend_access(
                self.member, self.owner, {'OEF Publishers'},
                reason='Publication duty', site_url='https://example.org/',
            )
        suspended = set_backend_access(
            self.member, self.owner, set(), reason='Duty ended',
            site_url='https://example.org/',
        )
        self.assertFalse(suspended.user.is_staff)
        self.assertFalse(suspended.user.groups.exists())
        self.engagement.refresh_from_db()
        self.assertEqual(self.engagement.status, Engagement.Status.ACTIVE)
        self.assertEqual(BackendAccessChange.objects.count(), 2)

    def test_admin_post_grants_then_removes_capability(self):
        self.activate_engagement()
        self.client.force_login(self.owner)
        url = reverse('admin:user_teammember_access', args=(self.member.pk,))
        with self.captureOnCommitCallbacks(execute=False):
            granted = self.client.post(url, {
                'groups': ['OEF Writers'], 'reason': 'Writing assignment', 'confirm': '1',
            })
        self.assertEqual(granted.status_code, 302)
        self.member.refresh_from_db()
        self.assertTrue(self.member.user.is_staff)
        removed = self.client.post(url, {
            'reason': 'Writing assignment ended', 'confirm': '1',
        })
        self.assertEqual(removed.status_code, 302)
        self.member.user.refresh_from_db()
        self.assertFalse(self.member.user.is_staff)
        self.assertFalse(self.member.user.groups.exists())
        self.assertEqual(BackendAccessChange.objects.count(), 2)
        self.assertContains(self.client.get(url), 'Access revoked')

    def test_effective_permission_preview_and_failed_invitation_retry(self):
        self.activate_engagement()
        self.writer.permissions.add(Permission.objects.get(
            content_type__app_label='blog', codename='submit_article',
        ))
        preview = preview_backend_access(self.member, self.owner, {'OEF Writers'})
        self.assertIn('blog.submit_article', preview['requested_permissions'])
        with self.captureOnCommitCallbacks(execute=False):
            result = set_backend_access(
                self.member, self.owner, {'OEF Writers'},
                reason='Content writing', site_url='https://example.org/',
            )
        with patch('user.access.send_email', side_effect=RuntimeError('Delivery unavailable')):
            failed = send_backend_invitation(result.invitation.pk, 'https://example.org/')
        self.assertEqual(failed.status, BackendAccessInvitation.Status.FAILED)
        self.assertEqual(failed.attempts, 1)
        self.assertEqual(BackendAccessChange.objects.count(), 1)
        with patch('user.access.send_email', return_value='message-123'):
            sent = send_backend_invitation(result.invitation.pk, 'https://example.org/')
        self.assertEqual(sent.status, BackendAccessInvitation.Status.SENT)
        self.assertEqual(sent.attempts, 2)
        self.assertEqual(BackendAccessChange.objects.count(), 1)
        with patch('user.access.send_email') as duplicate_send:
            unchanged = send_backend_invitation(result.invitation.pk, 'https://example.org/')
        self.assertEqual(unchanged.status, BackendAccessInvitation.Status.SENT)
        duplicate_send.assert_not_called()

    def test_in_flight_invitation_cannot_send_twice(self):
        self.activate_engagement()
        with self.captureOnCommitCallbacks(execute=False):
            result = set_backend_access(
                self.member, self.owner, {'OEF Writers'},
                reason='Writing duty', site_url='https://example.org/',
            )

        def check_second_attempt(*args, **kwargs):
            in_flight = send_backend_invitation(result.invitation.pk, 'https://example.org/')
            self.assertEqual(in_flight.status, BackendAccessInvitation.Status.SENDING)
            self.assertEqual(in_flight.attempts, 1)
            return 'message-123'

        with patch('user.access.send_email', side_effect=check_second_attempt) as delivery:
            sent = send_backend_invitation(result.invitation.pk, 'https://example.org/')
        self.assertEqual(sent.status, BackendAccessInvitation.Status.SENT)
        delivery.assert_called_once()
        self.assertEqual(
            delivery.call_args.kwargs['message_headers']['idempotencyKey'],
            str(result.invitation.key),
        )

    def test_stale_sending_invitation_recovers_with_same_delivery_key(self):
        self.activate_engagement()
        with self.captureOnCommitCallbacks(execute=False):
            result = set_backend_access(
                self.member, self.owner, {'OEF Writers'},
                reason='Writing duty', site_url='https://example.org/',
            )
        BackendAccessInvitation.objects.filter(pk=result.invitation.pk).update(
            status=BackendAccessInvitation.Status.SENDING,
            attempts=1,
            sending_started_at=timezone.now() - timedelta(minutes=16),
        )

        with patch('user.access.send_email', return_value='message-123') as delivery:
            sent = send_backend_invitation(result.invitation.pk, 'https://example.org/')
        self.assertEqual(sent.status, BackendAccessInvitation.Status.SENT)
        self.assertEqual(sent.attempts, 2)
        self.assertEqual(
            delivery.call_args.kwargs['message_headers']['idempotencyKey'],
            str(result.invitation.key),
        )

    def test_manager_cannot_edit_protected_target_or_grant_without_active_engagement(self):
        manager = UserProfile.objects.create_user(
            email='manager-two@example.org', password='test-password', is_staff=True,
        )
        manager.user_permissions.add(Permission.objects.get(
            content_type__app_label='user', codename='manage_team_access',
        ))
        protected = TeamMember.objects.create(
            user=self.owner, full_name='Owner', primary_email=self.owner.email,
            role_title='Founder',
        )
        with self.assertRaises(PermissionDenied):
            preview_backend_access(protected, manager, {'OEF Writers'})
        with self.assertRaises(ValidationError):
            set_backend_access(
                self.member, manager, {'OEF Writers'}, reason='Premature',
                site_url='https://example.org/',
            )

    def test_manager_has_curated_people_admin_but_not_raw_user_admin(self):
        manager = UserProfile.objects.create_user(
            email='manager@example.org', password='test-password', is_staff=True,
        )
        manager.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='user',
            codename__in=('manage_team_access', 'manage_team_engagement'),
        ))
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse('admin:user_teammember_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:user_engagement_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:user_userprofile_changelist')).status_code, 403)

    def test_access_records_are_contextual_and_engagements_are_not_in_admin_menu(self):
        self.activate_engagement()
        self.client.force_login(self.owner)
        self.assertFalse(admin.site.is_registered(BackendAccessChange))
        self.assertFalse(admin.site.is_registered(BackendAccessInvitation))
        request = RequestFactory().get('/bcx/')
        request.user = self.owner
        self.assertFalse(admin.site._registry[Engagement].has_module_permission(request))
        menu_models = {
            model['object_name']
            for app in admin.site.get_app_list(request)
            for model in app['models']
        }
        self.assertNotIn('Engagement', menu_models)
        self.assertNotIn('BackendAccessChange', menu_models)
        self.assertNotIn('BackendAccessInvitation', menu_models)
        self.assertEqual(
            self.client.get(reverse('admin:user_engagement_changelist')).status_code, 200,
        )
        member_page = self.client.get(reverse('admin:user_teammember_change', args=(self.member.pk,)))
        self.assertContains(member_page, 'View engagements')
        self.assertContains(member_page, 'Add engagement')
        self.assertContains(member_page, f'team_member__id__exact={self.member.pk}')
        other = TeamMember.objects.create(
            full_name='Other Member', primary_email='othermember@example.org',
        )
        Engagement.objects.create(team_member=other, role_title='Reviewer')
        engagements = self.client.get(
            reverse('admin:user_engagement_changelist')
            + f'?team_member__id__exact={self.member.pk}'
        )
        self.assertEqual(
            list(engagements.context['cl'].queryset.values_list('pk', flat=True)),
            [self.engagement.pk],
        )

        with self.captureOnCommitCallbacks(execute=False):
            set_backend_access(
                self.member, self.owner, {'OEF Writers'},
                reason='Writing assignment', site_url='https://example.org/',
            )
        access_page = self.client.get(reverse('admin:user_teammember_access', args=(self.member.pk,)))
        self.assertContains(access_page, 'Backend access log')
        self.assertContains(access_page, 'Access granted')
        self.assertContains(access_page, 'Access invitation')
        self.assertNotContains(access_page, 'effective permissions')

    def test_access_page_retries_only_its_members_invitation(self):
        self.activate_engagement()
        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=False):
            result = set_backend_access(
                self.member, self.owner, {'OEF Writers'},
                reason='Writing assignment', site_url='https://example.org/',
            )
        url = reverse('admin:user_teammember_access', args=(self.member.pk,))
        with patch('user.admin.send_backend_invitation') as retry:
            response = self.client.post(url, {'retry_invitation': str(result.invitation.pk)})
        self.assertEqual(response.status_code, 302)
        retry.assert_called_once()
        other = TeamMember.objects.create(full_name='Other', primary_email='other@example.org')
        Engagement.objects.create(team_member=other, role_title='Reviewer')
        self.assertEqual(
            self.client.post(
                reverse('admin:user_teammember_access', args=(other.pk,)),
                {'retry_invitation': str(result.invitation.pk)},
            ).status_code,
            403,
        )
        set_backend_access(
            self.member, self.owner, set(), reason='Writing assignment ended',
            site_url='https://example.org/',
        )
        with patch('user.admin.send_backend_invitation') as retry:
            self.assertEqual(
                self.client.post(url, {'retry_invitation': str(result.invitation.pk)}).status_code,
                403,
            )
        retry.assert_not_called()

    def test_access_page_does_not_retry_invitation_for_superseded_account(self):
        self.activate_engagement()
        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=False):
            result = set_backend_access(
                self.member, self.owner, {'OEF Writers'},
                reason='Writing assignment', site_url='https://example.org/',
            )
        replacement = UserProfile.objects.create_user(
            email='replacement@example.org', password='test-password', is_staff=True,
        )
        replacement.groups.add(self.writer)
        self.member.user = replacement
        self.member.save(update_fields=('user',))
        url = reverse('admin:user_teammember_access', args=(self.member.pk,))
        page = self.client.get(url)
        self.assertNotContains(page, 'Send or retry')
        with patch('user.admin.send_backend_invitation') as retry:
            response = self.client.post(url, {
                'retry_invitation': str(result.invitation.pk),
            })
        self.assertEqual(response.status_code, 403)
        retry.assert_not_called()
        with patch('user.access.send_email') as delivery:
            unchanged = send_backend_invitation(result.invitation.pk, 'https://example.org/')
        delivery.assert_not_called()
        self.assertEqual(unchanged.attempts, 0)

    def test_disabled_account_cannot_receive_pending_invitation(self):
        self.activate_engagement()
        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=False):
            result = set_backend_access(
                self.member, self.owner, {'OEF Writers'},
                reason='Writing assignment', site_url='https://example.org/',
            )
        account = result.user
        account.is_active = False
        account.save(update_fields=('is_active',))
        url = reverse('admin:user_teammember_access', args=(self.member.pk,))
        self.assertNotContains(self.client.get(url), 'Send or retry')
        with patch('user.admin.send_backend_invitation') as retry:
            self.assertEqual(
                self.client.post(url, {
                    'retry_invitation': str(result.invitation.pk),
                }).status_code,
                403,
            )
        retry.assert_not_called()
        with patch('user.access.send_email') as delivery:
            unchanged = send_backend_invitation(result.invitation.pk, 'https://example.org/')
        delivery.assert_not_called()
        self.assertEqual(unchanged.attempts, 0)
