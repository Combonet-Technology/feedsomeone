"""Exercise the admin actions and their actual emailed links with isolated users."""
import re
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase
from django.urls import reverse

from user.models import (BackendAccessInvitation, Engagement, TeamMember,
                         UserProfile)


class AccessLifecycleTests(TestCase):
    def setUp(self):
        owner = UserProfile.objects.create_superuser(email='owner@example.org', password='test')
        self.account = UserProfile.objects.create_user(
            email='lifecycle@oluwafemiebenezerfoundation.org',
        )
        member = TeamMember.objects.create(
            user=self.account, full_name='Lifecycle test', primary_email='personal@example.org',
        )
        Engagement.objects.create(team_member=member, role_title='Writer', status='active')
        self.client.force_login(owner)
        self.access_url = reverse('admin:user_teammember_access', args=[member.pk])
        self.admin_url = reverse('admin:index')
        self.login_url = reverse('admin:login')
        mail_patch = patch('user.access.send_email', return_value='captured-test-email')
        self.mail = mail_patch.start()
        self.addCleanup(mail_patch.stop)

    def action(self, action):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.access_url, {
                'action': action, 'reason': 'Lifecycle verification', 'confirm_action': 'on',
            })
        self.assertRedirects(response, self.access_url)

    def email_link(self):
        payload = self.mail.call_args.kwargs
        self.assertEqual(payload['destination'], self.account.email)
        url, = re.findall(r'https?://\S+', payload['text_content'])
        return urlsplit(url).path

    def open_password_form(self, client, link):
        response = client.get(link)
        self.assertEqual(response.status_code, 302)
        form_url = response['Location']
        self.assertContains(client.get(form_url), 'name="new_password1"')
        return form_url

    def save_password(self, client, form_url, password):
        response = client.post(form_url, {'new_password1': password, 'new_password2': password})
        self.assertRedirects(response, self.admin_url)

    def login(self, password, allowed=True):
        client = Client()
        response = client.post(self.login_url, {
            'username': self.account.email, 'password': password, 'next': self.admin_url,
        })
        self.assertEqual(response.status_code, 302 if allowed else 200)
        self.assertEqual(client.get(self.admin_url).status_code, 200 if allowed else 302)
        return client

    def test_grant_login_suspend_restore_resend_and_password_reset(self):
        password = 'First-Strong-Password-829!'
        replacement = 'Replacement-Strong-Password-941!'
        self.action('grant')
        self.assertEqual(self.mail.call_count, 1)
        invitation = BackendAccessInvitation.objects.get()
        self.assertEqual(invitation.status, 'sent')
        link = self.email_link()
        setup_client = Client()
        form_url = self.open_password_form(setup_client, link)
        self.save_password(setup_client, form_url, password)
        self.assertEqual(Client().get(link).status_code, 400)
        session = self.login(password)

        self.action('suspend')
        self.assertEqual(session.get(self.admin_url).status_code, 302)
        self.login(password, allowed=False)
        self.account.refresh_from_db()
        self.assertTrue(self.account.is_active)
        self.assertFalse(self.account.is_staff)
        self.action('resume')
        self.assertEqual(self.mail.call_count, 1)
        session = self.login(password)

        self.action('resend')
        self.assertEqual(self.mail.call_count, 2)
        # Existing-password accounts receive the login page, not a bearer credential.
        self.assertEqual(self.email_link(), self.admin_url)
        self.assertEqual(Client().get(self.email_link()).status_code, 302)

        self.action('reset')
        self.assertEqual(self.mail.call_count, 3)
        reset_link = self.email_link()
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password(password))
        reset_client = Client()
        reset_form = self.open_password_form(reset_client, reset_link)
        self.save_password(reset_client, reset_form, replacement)
        self.assertEqual(session.get(self.admin_url).status_code, 302)
        self.login(password, allowed=False)
        self.login(replacement)
        self.assertEqual(Client().get(reset_link).status_code, 400)
        self.assertEqual(reset_client.post(reset_form, {
            'new_password1': password, 'new_password2': password,
        }).status_code, 400)

    def test_unused_and_opened_setup_link_expire_and_resend_replaces_them(self):
        now = datetime(2026, 9, 27, 12)
        self.assertGreater(settings.PASSWORD_RESET_TIMEOUT, 0)
        with patch.object(default_token_generator, '_now', return_value=now):
            self.action('grant')
            expired_link = self.email_link()
            original_client = Client()
            expired_form = self.open_password_form(original_client, expired_link)
        later = now + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1)
        with patch.object(default_token_generator, '_now', return_value=later):
            self.assertEqual(Client().get(expired_link).status_code, 400)
            self.assertEqual(original_client.post(expired_form, {
                'new_password1': 'Strong-Unused-Password-827!',
                'new_password2': 'Strong-Unused-Password-827!',
            }).status_code, 400)
            self.account.refresh_from_db()
            self.assertFalse(self.account.has_usable_password())
            self.action('resend')
            replacement = self.email_link()
            self.assertNotEqual(replacement, expired_link)
            # Replacement invalidates the first invitation independently of its age.
            with patch.object(default_token_generator, '_now', return_value=now):
                self.assertEqual(Client().get(expired_link).status_code, 400)
            client = Client()
            form = self.open_password_form(client, replacement)
            self.save_password(client, form, 'Strong-Reissued-Password-762!')

    def test_reset_link_expires_without_changing_existing_password(self):
        password = 'Existing-Strong-Password-982!'
        self.account.set_password(password)
        self.account.save(update_fields=['password'])
        self.action('grant')
        now = datetime(2026, 9, 27, 12)
        with patch.object(default_token_generator, '_now', return_value=now):
            self.action('reset')
            link = self.email_link()
            client = Client()
            form = self.open_password_form(client, link)
        later = now + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1)
        with patch.object(default_token_generator, '_now', return_value=later):
            self.assertEqual(Client().get(link).status_code, 400)
            self.assertEqual(client.post(form, {
                'new_password1': 'Unaccepted-Password-483!',
                'new_password2': 'Unaccepted-Password-483!',
            }).status_code, 400)
        self.login(password)
