from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from user.models import TeamMember, UserProfile

from .models import Vacancy, VacancyApplication
from .staff_access import (StaffAccessNotEligible, grant_staff_access,
                           revoke_staff_access)


class StaffAccessWorkflowTests(TestCase):
    def setUp(self):
        self.group = Group.objects.get(name='Recruitment Manager')
        self.owner = UserProfile.objects.create_superuser(
            email='owner@example.com',
            password='owner-test-password',
        )
        self.vacancy = Vacancy.objects.create(
            title='Grant and Research Writer',
            slug='grant-writer-staff-access-test',
            team='Grants and Research',
            summary='Research funding opportunities.',
            description='Support OEF grant readiness.',
            expectations='Work independently.',
            responsibilities='Research grants.',
            benefits='Practical nonprofit experience.',
            who_we_are_looking_for='A careful researcher.',
            engagement_type='volunteer',
            status='open',
        )
        self.application = VacancyApplication.objects.create(
            vacancy=self.vacancy,
            full_name='Temitope Florence Ademiju',
            email='florence@example.com',
            cv='vacancy_applications/private_cv/florence.pdf',
            cover_letter='I would like to contribute.',
            status='agreement_signed',
        )
        self.form_data = {
            'role_title': self.vacancy.title,
            'engagement_type': 'volunteer',
            'start_date': date(2026, 7, 31),
            'confirm_grant': True,
        }

    @patch('opportunities.staff_access.send_email', return_value='message-123')
    def test_grant_creates_linked_account_team_member_and_invitation(self, send_email):
        result = grant_staff_access(
            self.application,
            self.form_data,
            self.owner,
            'http://testserver/',
        )

        self.application.refresh_from_db()
        user = self.application.applicant
        self.assertTrue(result.account_created)
        self.assertTrue(result.password_setup_required)
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.groups.filter(pk=self.group.pk).exists())
        self.assertEqual(result.team_member.source_application, self.application)
        self.assertEqual(result.team_member.status, 'invited')
        self.assertEqual(result.team_member.invitation_message_id, 'message-123')
        self.assertIsNotNone(result.team_member.invitation_sent_at)
        email = send_email.call_args.kwargs
        self.assertEqual(email['destination'], 'florence@example.com')
        self.assertIn('/staff-access/activate/', email['text_content'])

    @patch('opportunities.staff_access.send_email', return_value='message-456')
    def test_grant_reuses_existing_account_without_duplicate_records(self, send_email):
        user = UserProfile.objects.create_user(
            email=self.application.email,
            password='existing-test-password',
        )

        first = grant_staff_access(
            self.application,
            self.form_data,
            self.owner,
            'http://testserver/',
        )
        second = grant_staff_access(
            self.application,
            self.form_data,
            self.owner,
            'http://testserver/',
        )

        self.application.refresh_from_db()
        self.assertEqual(self.application.applicant, user)
        self.assertFalse(first.account_created)
        self.assertFalse(first.password_setup_required)
        self.assertEqual(first.team_member.pk, second.team_member.pk)
        self.assertEqual(UserProfile.objects.filter(email=self.application.email).count(), 1)
        self.assertEqual(TeamMember.objects.filter(user=user).count(), 1)
        self.assertEqual(send_email.call_count, 2)
        self.assertIn('/bcx/', send_email.call_args.kwargs['text_content'])

    @patch('opportunities.staff_access.send_email', side_effect=RuntimeError('Email unavailable'))
    def test_delivery_failure_is_recorded_without_discarding_access(self, send_email):
        with self.assertRaises(RuntimeError):
            grant_staff_access(
                self.application,
                self.form_data,
                self.owner,
                'http://testserver/',
            )

        self.application.refresh_from_db()
        member = TeamMember.objects.get(source_application=self.application)
        self.assertTrue(self.application.applicant.is_staff)
        self.assertTrue(self.application.applicant.groups.filter(pk=self.group.pk).exists())
        self.assertIn('Email unavailable', member.invitation_error)

    @patch('opportunities.staff_access.send_email', return_value='message-123')
    def test_revoke_removes_permission_but_retains_records(self, send_email):
        result = grant_staff_access(
            self.application,
            self.form_data,
            self.owner,
            'http://testserver/',
        )

        revoke_staff_access(self.application, self.owner)

        result.team_member.refresh_from_db()
        result.team_member.user.refresh_from_db()
        self.assertEqual(result.team_member.status, 'inactive')
        self.assertIsNotNone(result.team_member.access_revoked_at)
        self.assertFalse(result.team_member.user.is_staff)
        self.assertFalse(result.team_member.user.groups.filter(pk=self.group.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=result.team_member.user_id).exists())
        self.assertTrue(VacancyApplication.objects.filter(pk=self.application.pk).exists())

    def test_received_application_is_not_eligible(self):
        self.application.status = 'received'
        self.application.save(update_fields=('status', 'updated_at'))

        with self.assertRaises(StaffAccessNotEligible):
            grant_staff_access(
                self.application,
                self.form_data,
                self.owner,
                'http://testserver/',
            )

    def test_recruitment_manager_cannot_open_staff_access_control(self):
        manager = UserProfile.objects.create_user(
            email='manager@example.com',
            password='manager-test-password',
            is_staff=True,
        )
        manager.groups.add(self.group)
        self.client.force_login(manager)

        response = self.client.get(
            reverse(
                'admin:opportunities_vacancyapplication_staff_access',
                args=(self.application.pk,),
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_staff_access_action_is_visible_but_disabled_for_recruitment_manager(self):
        manager = UserProfile.objects.create_user(
            email='visible-manager@example.com',
            password='manager-test-password',
            is_staff=True,
        )
        manager.groups.add(self.group)
        self.client.force_login(manager)

        response = self.client.get(
            reverse(
                'admin:opportunities_vacancyapplication_change',
                args=(self.application.pk,),
            )
        )

        self.assertContains(response, 'Grant staff access')
        self.assertNotContains(response, 'Restore staff access')
        self.assertNotContains(response, 'Resend access email')
        self.assertNotContains(response, 'Revoke staff access')
        self.assertContains(response, 'Only the OEF superuser can grant or revoke staff access.')

    def test_staff_access_action_is_disabled_before_agreement_is_signed(self):
        self.application.status = 'reviewing'
        self.application.save(update_fields=('status', 'updated_at'))
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                'admin:opportunities_vacancyapplication_change',
                args=(self.application.pk,),
            )
        )

        self.assertContains(response, 'Grant staff access')
        self.assertNotContains(response, 'Restore staff access')
        self.assertNotContains(response, 'Resend access email')
        self.assertNotContains(response, 'Revoke staff access')
        self.assertContains(
            response,
            'The volunteer agreement must be signed before staff access is granted.',
        )

    @patch('opportunities.staff_access.send_email', return_value='message-123')
    def test_superuser_can_grant_access_from_application_admin(self, send_email):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                'admin:opportunities_vacancyapplication_staff_access',
                args=(self.application.pk,),
            ),
            {
                'action': 'grant',
                'role_title': self.vacancy.title,
                'engagement_type': 'volunteer',
                'start_date': '2026-07-31',
                'confirm_grant': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TeamMember.objects.filter(source_application=self.application).exists())

    @patch('opportunities.staff_access.send_email', return_value='message-123')
    def test_granted_access_exposes_resend_and_revoke_actions(self, send_email):
        grant_staff_access(
            self.application,
            self.form_data,
            self.owner,
            'http://testserver/',
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                'admin:opportunities_vacancyapplication_change',
                args=(self.application.pk,),
            )
        )

        self.assertContains(response, 'Resend access email')
        self.assertContains(response, 'Revoke staff access')
        self.assertNotContains(response, 'Grant staff access')
        self.assertNotContains(response, 'Restore staff access')
        self.assertContains(response, '#revoke-access')

    @patch('opportunities.staff_access.send_email', return_value='message-123')
    def test_revoked_access_exposes_restore_and_disables_revoke(self, send_email):
        grant_staff_access(
            self.application,
            self.form_data,
            self.owner,
            'http://testserver/',
        )
        revoke_staff_access(self.application, self.owner)
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                'admin:opportunities_vacancyapplication_change',
                args=(self.application.pk,),
            )
        )

        self.assertContains(response, 'Restore staff access')
        self.assertNotContains(response, 'Grant staff access')
        self.assertNotContains(response, 'Resend access email')
        self.assertNotContains(response, 'Revoke staff access')


class StaffAccessActivationTests(TestCase):
    @patch('opportunities.staff_access.send_email', return_value='message-123')
    def test_invited_user_sets_password_and_enters_onboarding(self, send_email):
        owner = UserProfile.objects.create_superuser(
            email='owner@example.com',
            password='owner-test-password',
        )
        vacancy = Vacancy.objects.create(
            title='Project Manager',
            slug='project-manager-activation-test',
            summary='Coordinate projects.',
            description='Coordinate delivery.',
            expectations='Work independently.',
            responsibilities='Manage tasks.',
            benefits='Practical experience.',
            who_we_are_looking_for='An organised coordinator.',
            status='open',
        )
        application = VacancyApplication.objects.create(
            vacancy=vacancy,
            full_name='New Manager',
            email='new-manager@example.com',
            cv='vacancy_applications/private_cv/manager.pdf',
            cover_letter='I would like to contribute.',
            status='agreement_signed',
        )
        result = grant_staff_access(
            application,
            {
                'role_title': vacancy.title,
                'engagement_type': 'volunteer',
                'start_date': None,
                'confirm_grant': True,
            },
            owner,
            'http://testserver/',
        )
        invitation_url = send_email.call_args.kwargs['text_content'].splitlines()[5]

        response = self.client.get(invitation_url)
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            response.request['PATH_INFO'],
            {
                'new_password1': 'A-secure-staff-password-2468',
                'new_password2': 'A-secure-staff-password-2468',
            },
        )

        self.assertRedirects(response, reverse('admin:index'))
        result.team_member.refresh_from_db()
        result.team_member.user.refresh_from_db()
        self.assertEqual(result.team_member.status, 'onboarding')
        self.assertIsNotNone(result.team_member.activated_at)
        self.assertTrue(result.team_member.user.check_password('A-secure-staff-password-2468'))
