from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from user.access import send_backend_invitation, set_backend_access
from user.models import (BackendAccessChange, BackendAccessInvitation,
                         Engagement, TeamMember, UserProfile)


class ManualAccessTests(TestCase):
    def setUp(self):
        self.owner = UserProfile.objects.create_superuser(email='owner@example.org', password='test')
        self.account = UserProfile.objects.create_user(email='member@oluwafemiebenezerfoundation.org')
        self.member = TeamMember.objects.create(
            user=self.account, full_name='Member', primary_email='personal@example.org',
        )
        Engagement.objects.create(team_member=self.member, role_title='Writer', status='active')
        self.client.force_login(self.owner)
        self.url = reverse('admin:user_teammember_access', args=[self.member.pk])

    def action(self, action, groups=None):
        with self.captureOnCommitCallbacks(execute=False):
            return set_backend_access(self.member, self.owner, groups, action=action,
                                      reason='Approved test action', site_url='https://example.org/')

    def invitation_url(self, invitation):
        self.account.refresh_from_db()
        return reverse('member_access_activate', args=[
            invitation.key, urlsafe_base64_encode(force_bytes(self.account.pk)),
            default_token_generator.make_token(self.account),
        ])

    def test_configuration_does_not_enable_access_or_email(self):
        with self.captureOnCommitCallbacks(execute=True), patch('user.access.send_email') as mail:
            self.action('configure', ['OEF Writers', 'OEF Writers'])
        self.account.refresh_from_db()
        self.member.refresh_from_db()
        self.assertFalse(self.account.is_staff)
        self.assertFalse(self.account.groups.exists())
        self.assertEqual(self.member.desired_backend_groups, ['OEF Writers'])
        self.assertFalse(BackendAccessInvitation.objects.exists())
        mail.assert_not_called()

    def test_personal_email_cannot_receive_staff_grant(self):
        self.account.email = 'personal@example.org'
        self.account.save(update_fields=['email'])
        with self.assertRaisesMessage(ValidationError, 'workspace email'):
            self.action('grant')
        self.assertFalse(BackendAccessInvitation.objects.exists())

    def test_access_page_has_no_email_editor_and_rejects_email_change_posts(self):
        page = self.client.get(self.url)
        self.assertNotContains(page, 'Change login email')
        self.assertNotContains(page, 'Update login email')
        self.assertNotContains(page, 'name="email"')
        self.assertContains(page, 'Reason:')
        response = self.client.post(self.url, {
            'action': 'login_email', 'email': 'not-an-email', 'confirm_email': 'on', 'reason': 'Test',
        })
        self.assertEqual(response.status_code, 403)
        self.account.refresh_from_db()
        self.assertEqual(self.account.email, 'member@oluwafemiebenezerfoundation.org')

    def test_zero_preset_grant_and_idempotence_are_audited(self):
        result = self.action('grant')
        self.assertTrue(result.user.is_staff)
        self.assertFalse(result.user.groups.exists())
        audit = BackendAccessChange.objects.get()
        self.assertFalse(audit.before_enabled)
        self.assertTrue(audit.after_enabled)
        self.assertIsNotNone(result.invitation)
        self.assertFalse(self.action('grant').changed)
        self.assertEqual(BackendAccessInvitation.objects.count(), 1)

    def test_suspend_configure_resume_preserves_only_desired_capabilities(self):
        self.action('configure', ['OEF Writers'])
        self.action('grant')
        self.action('suspend')
        self.account.refresh_from_db()
        self.assertTrue(self.account.is_active)
        self.assertFalse(self.account.is_staff)
        self.assertFalse(self.account.groups.exists())
        self.action('configure', ['OEF Reviewers'])
        self.assertFalse(self.account.groups.exists())
        result = self.action('resume')
        self.assertTrue(result.user.is_staff)
        self.assertEqual(list(result.user.groups.values_list('name', flat=True)), ['OEF Reviewers'])
        self.assertIsNone(result.invitation)
        self.assertEqual(BackendAccessInvitation.objects.count(), 1)

    def test_permission_edits_while_enabled_do_not_send_and_empty_does_not_suspend(self):
        self.action('grant')
        self.action('configure', ['OEF Publishers'])
        result = self.action('configure', [])
        self.assertTrue(result.user.is_staff)
        self.assertFalse(result.user.groups.exists())
        self.assertEqual(BackendAccessInvitation.objects.count(), 1)

    def test_suspend_resume_does_not_restore_old_setup_link(self):
        invitation = self.action('grant').invitation
        url = self.invitation_url(invitation)
        self.action('suspend')
        self.assertEqual(self.client.get(url).status_code, 400)
        self.action('resume')
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_email_change_disabled_or_relinked_account_invalidates_invitation(self):
        invitation = self.action('grant').invitation
        url = self.invitation_url(invitation)
        self.account.email = 'new@oluwafemiebenezerfoundation.org'
        self.account.save(update_fields=['email'])
        self.assertEqual(self.client.get(url).status_code, 400)
        invitation = self.action('resend').invitation
        url = self.invitation_url(invitation)
        self.account.is_active = False
        self.account.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(url).status_code, 400)
        self.account.is_active = True
        self.account.save(update_fields=['is_active'])
        self.member.user = UserProfile.objects.create_user(email='other@example.org')
        self.member.save(update_fields=['user'])
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_sent_invitation_can_be_reissued_with_new_key_and_version(self):
        old = self.action('grant').invitation
        old_url = self.invitation_url(old)
        with patch('user.access.send_email', return_value='id'):
            send_backend_invitation(old.pk, 'https://example.org/')
        new = self.action('resend').invitation
        self.assertNotEqual(old.key, new.key)
        self.assertGreater(new.access_version, old.access_version)
        old.refresh_from_db()
        self.assertEqual(old.status, 'sent')
        self.assertEqual(self.client.get(old_url).status_code, 400)

    def test_password_errors_remain_visible_and_success_consumes_link(self):
        invitation = self.action('grant').invitation
        client = Client()
        response = client.get(self.invitation_url(invitation))
        self.assertEqual(response.status_code, 302)
        url = response.url
        invalid = client.post(url, {'new_password1': 'Strong-pass-123!', 'new_password2': 'different'})
        self.assertEqual(invalid.status_code, 200)
        self.assertTrue(invalid.context['form'].errors)
        response = client.post(url, {'new_password1': 'Strong-pass-123!', 'new_password2': 'Strong-pass-123!'})
        self.assertRedirects(response, reverse('admin:index'), fetch_redirect_response=False)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.used_at)
        self.assertEqual(client.post(url, {}).status_code, 400)

    def test_existing_password_notice_vs_explicit_reset(self):
        self.account.set_password('Existing-password-123!')
        self.account.save()
        invitation = self.action('grant').invitation
        with patch('user.access.send_email', return_value='id') as mail:
            send_backend_invitation(invitation.pk, 'https://example.org/')
        self.assertIn('/bcx/', mail.call_args.kwargs['text_content'])
        self.assertNotIn('/access/', mail.call_args.kwargs['text_content'])
        reset = self.action('reset').invitation
        with patch('user.access.send_email', return_value='id') as mail:
            send_backend_invitation(reset.pk, 'https://example.org/')
        self.assertIn('/access/', mail.call_args.kwargs['text_content'])
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password('Existing-password-123!'))

    def test_removed_profile_invitation_action_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.action('invite_profile')
        self.assertFalse(BackendAccessInvitation.objects.exists())

    def test_failed_email_has_simple_feedback_without_rendering_internal_log(self):
        invitation = self.action('grant').invitation
        BackendAccessInvitation.objects.filter(pk=invitation.pk).update(status='failed', error='private-provider-error')
        from user.access import AccessResult
        with patch('user.admin.set_backend_access', return_value=AccessResult(self.account, True, invitation)):
            page = self.client.post(self.url, {
                'action': 'resend', 'reason': 'Retry', 'confirm_action': 'on',
            }, follow=True)
        self.assertContains(page, 'email could not be sent')
        self.assertNotContains(page, 'private-provider-error')
        self.assertNotContains(page, 'Backend access log')

    def test_team_member_has_three_distinct_management_destinations(self):
        page = self.client.get(reverse('admin:user_teammember_change', args=[self.member.pk]))
        permissions_url = reverse('admin:user_teammember_permissions', args=[self.member.pk])
        self.assertContains(page, f'href="{self.url}">Manage access</a>', html=False)
        self.assertContains(page, f'href="{permissions_url}">Manage permissions</a>', html=False)
        self.assertContains(page, 'Manage engagements')
        self.assertNotContains(page, 'Private profile')
        self.assertNotContains(page, 'My member profile')
        access = self.client.get(self.url)
        for label in ('Grant access', 'Suspend access', 'Restore access', 'Resend login link', 'Reset password'):
            self.assertContains(access, label)
        self.assertNotContains(access, 'Capability presets')
        self.assertNotContains(access, 'Send member profile')
        permissions = self.client.get(permissions_url)
        self.assertContains(permissions, 'Capability presets')
        self.assertNotContains(permissions, 'Apply access action')
        self.assertNotContains(permissions, 'Update login email')
        self.assertEqual(self.client.post(permissions_url, {
            'action': 'grant', 'reason': 'Test', 'confirm_action': 'on',
        }).status_code, 403)
        self.assertEqual(self.client.post(self.url, {
            'action': 'configure', 'groups': ['OEF Writers'], 'reason': 'Test', 'confirm': '1',
        }).status_code, 403)
        self.account.refresh_from_db()
        self.assertFalse(self.account.is_staff)
        self.assertFalse(BackendAccessInvitation.objects.exists())

    def test_private_profile_routes_and_models_are_removed(self):
        from django.apps import apps
        for name in ('MemberDetails', 'MemberDocument', 'MemberProfileRevision'):
            with self.assertRaises(LookupError):
                apps.get_model('user', name)
        for path in ('/members/profile/', '/members/documents/1/'):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertFalse(Permission.objects.filter(codename='manage_private_profiles').exists())

    def test_admin_requires_explicit_confirmed_action(self):
        response = self.client.post(self.url, {'action': 'grant', 'reason': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.account.refresh_from_db()
        self.assertFalse(self.account.is_staff)
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(self.url, {'action': 'grant', 'reason': 'Test', 'confirm_action': 'on'})
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.assertTrue(self.account.is_staff)

    def test_zero_preset_grant_requires_active_engagement_and_legacy_links_are_closed(self):
        self.member.engagements.update(status='ended')
        with self.assertRaises(ValidationError):
            self.action('grant')
        old_url = reverse('staff_access_activate', args=[
            urlsafe_base64_encode(force_bytes(self.account.pk)), default_token_generator.make_token(self.account),
        ])
        self.assertEqual(self.client.get(old_url).status_code, 400)

    def test_tampered_desired_groups_cannot_be_restored(self):
        self.member.desired_backend_groups = ['Unapproved managers']
        self.member.save(update_fields=['desired_backend_groups'])
        with self.assertRaises(ValidationError):
            self.action('resume')

    def test_csrf_and_ordinary_account_cannot_manage_access(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, {'action': 'grant'}).status_code, 403)
        self.client.force_login(self.account)
        self.assertEqual(self.client.post(self.url, {'action': 'grant'}).status_code, 302)

    def test_suspension_during_delivery_makes_the_link_unusable(self):
        invitation = self.action('grant').invitation
        url = self.invitation_url(invitation)

        def delivery(**kwargs):
            self.action('suspend')
            return 'provider-accepted'
        with patch('user.access.send_email', side_effect=delivery):
            result = send_backend_invitation(invitation.pk, 'https://example.org/')
        self.assertEqual(result.status, 'sent')
        self.assertEqual(self.client.get(url).status_code, 400)
