from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from opportunities.models import Vacancy, VacancyApplication
from user.models import Engagement, TeamMember, UserProfile
from user.workforce import APPOINTMENT_STATUSES, appoint_candidate


class ApplicationPrefillTests(TestCase):
    def setUp(self):
        self.owner = UserProfile.objects.create_superuser(email='owner@example.org', password='test')
        self.vacancy = Vacancy.objects.create(title='Content Writer', slug='prefill-role')
        self.application = VacancyApplication.objects.create(
            vacancy=self.vacancy, full_name='Applicant Name', email='applicant@example.org',
            status=VacancyApplication.Status.OFFER_ACCEPTED, cover_letter='I would like to help.',
            cv='vacancy-applications/test.pdf',
        )
        self.client.force_login(self.owner)
        self.add_url = reverse('admin:user_teammember_add')
        self.preview_url = reverse('admin:user_teammember_application_preview')
        self.data = {
            'application': self.application.pk, 'full_name': 'Confirmed Name',
            'primary_email': 'confirmed@example.org', 'role_title': 'Programme Coordinator',
            'engagement_type': 'volunteer', '_save': 'Save',
        }

    def test_selector_and_preview_use_only_eligible_unused_applications(self):
        self.assertIsNotNone(finders.find('user/team_member_application.js'))
        for status in VacancyApplication.Status.values:
            with self.subTest(status=status):
                VacancyApplication.objects.filter(pk=self.application.pk).update(status=status)
                response = self.client.get(self.add_url)
                choices = response.context['adminform'].form.fields['application'].queryset
                self.assertEqual(choices.filter(pk=self.application.pk).exists(), status in APPOINTMENT_STATUSES)
                preview = self.client.get(self.preview_url, {'application': self.application.pk})
                self.assertEqual(preview.status_code, 200 if status in APPOINTMENT_STATUSES else 404)
        VacancyApplication.objects.filter(pk=self.application.pk).update(status=APPOINTMENT_STATUSES[0])
        preview = self.client.get(self.preview_url, {'application': self.application.pk})
        self.assertEqual(preview.json(), {
            'full_name': 'Applicant Name', 'primary_email': 'applicant@example.org',
            'role_title': 'Content Writer', 'engagement_type': self.vacancy.engagement_type,
        })
        self.assertIn('no-store', preview['Cache-Control'])
        self.assertEqual(self.client.get(self.preview_url, {'application': 'bad'}).status_code, 404)
        self.assertFalse(TeamMember.objects.exists())

    def test_save_appoints_once_with_editable_defaults_and_provenance(self):
        response = self.client.post(self.add_url, self.data)
        self.assertEqual(response.status_code, 302)
        member = TeamMember.objects.get()
        engagement = member.engagements.get()
        self.assertEqual(member.full_name, 'Confirmed Name')
        self.assertEqual(member.primary_email, 'confirmed@example.org')
        self.assertEqual(member.source_application_id, self.application.pk)
        self.assertEqual(engagement.source_application_id, self.application.pk)
        self.assertEqual(engagement.role_title, 'Programme Coordinator')
        self.assertFalse(member.user.is_staff)
        self.assertFalse(member.user.groups.exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.APPOINTED)
        self.assertEqual(self.application.full_name, 'Applicant Name')
        self.assertEqual(self.application.email, 'applicant@example.org')
        self.assertEqual(self.application.applicant_id, member.user_id)
        self.assertEqual(self.client.post(self.add_url, self.data).status_code, 200)
        self.assertEqual(TeamMember.objects.count(), 1)
        self.assertEqual(Engagement.objects.count(), 1)
        change = self.client.get(reverse('admin:user_teammember_change', args=[member.pk]))
        self.assertNotIn('application', change.context['adminform'].form.fields)
        self.assertContains(change, 'View vacancy application')
        application_edit = self.client.post(
            reverse('admin:opportunities_vacancyapplication_change', args=[self.application.pk]),
            {'vacancy': self.vacancy.pk, 'full_name': self.application.full_name,
             'email': self.application.email, 'cover_letter': self.application.cover_letter,
             'status': VacancyApplication.Status.APPOINTED, '_save': 'Save'},
        )
        self.assertEqual(application_edit.status_code, 302, (
            application_edit.context['adminform'].form.errors if application_edit.context else ''
        ))

    def test_historical_link_falls_back_only_to_an_unambiguous_engagement(self):
        engagement = appoint_candidate(self.application, self.owner)
        member = engagement.team_member
        member.source_application = None
        member.save(update_fields=['source_application'])
        url = reverse('admin:user_teammember_change', args=[member.pk])
        self.assertContains(self.client.get(url), 'View vacancy application')
        other = VacancyApplication.objects.create(
            vacancy=self.vacancy, full_name='Other', email='other@example.org',
        )
        Engagement.objects.create(
            team_member=member, source_application=other, role_title='Another role', status=Engagement.Status.ENDED,
        )
        response = self.client.get(url)
        self.assertContains(response, 'Multiple vacancy applications exist')
        self.assertNotContains(response, 'View vacancy application')

    def test_service_rejects_every_ineligible_new_appointment(self):
        for status in set(VacancyApplication.Status.values) - set(APPOINTMENT_STATUSES):
            with self.subTest(status=status):
                VacancyApplication.objects.filter(pk=self.application.pk).update(status=status)
                with self.assertRaisesMessage(ValidationError, 'not eligible'):
                    appoint_candidate(self.application, self.owner)
        self.assertFalse(TeamMember.objects.exists())
        self.assertEqual(UserProfile.objects.count(), 1)

    def test_application_admin_rejects_early_appointment_as_form_error(self):
        self.application.status = VacancyApplication.Status.RECEIVED
        self.application.save()
        response = self.client.post(
            reverse('admin:opportunities_vacancyapplication_change', args=[self.application.pk]),
            {'vacancy': self.vacancy.pk, 'full_name': self.application.full_name,
             'email': self.application.email, 'status': VacancyApplication.Status.APPOINTED, '_save': 'Save'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not eligible for appointment')
        self.assertFalse(TeamMember.objects.exists())

    def test_linked_account_is_reused_but_cannot_have_its_email_overridden(self):
        account = UserProfile.objects.create_user(email=self.application.email)
        self.application.applicant = account
        self.application.save()
        self.assertEqual(self.client.post(self.add_url, self.data).status_code, 200)
        self.assertFalse(TeamMember.objects.exists())
        self.data['primary_email'] = account.email
        self.assertEqual(self.client.post(self.add_url, self.data).status_code, 302)
        self.assertEqual(TeamMember.objects.get().user_id, account.pk)
        self.assertEqual(UserProfile.objects.count(), 2)

    def test_stale_selection_does_not_create_a_direct_member(self):
        self.application.status = VacancyApplication.Status.WITHDRAWN
        self.application.save()
        response = self.client.post(self.add_url, self.data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TeamMember.objects.exists())
        self.assertFalse(Engagement.objects.exists())

    def test_service_failure_is_a_bound_form_error_and_rolls_back(self):
        with patch('user.admin.appoint_candidate', side_effect=ValidationError('Appointment changed. Retry.')):
            response = self.client.post(self.add_url, self.data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Appointment changed. Retry.')
        self.assertEqual(response.context['adminform'].form.data['full_name'], 'Confirmed Name')
        self.assertFalse(TeamMember.objects.exists())

    def test_engagement_manager_without_recruitment_permission_cannot_read_or_select_application(self):
        manager = UserProfile.objects.create_user(email='manager@example.org', is_staff=True)
        manager.user_permissions.add(Permission.objects.get(codename='manage_team_engagement'))
        self.client.force_login(manager)
        response = self.client.get(self.add_url)
        self.assertFalse(response.context['adminform'].form.fields['application'].queryset.exists())
        self.assertEqual(self.client.get(self.preview_url, {'application': self.application.pk}).status_code, 403)
        self.assertEqual(self.client.post(self.add_url, self.data).status_code, 200)
        self.assertFalse(TeamMember.objects.exists())

    def test_manual_member_has_absence_text_and_edit_cannot_select_application(self):
        self.data.pop('application')
        self.assertEqual(self.client.post(self.add_url, self.data).status_code, 302)
        member = TeamMember.objects.get()
        url = reverse('admin:user_teammember_change', args=[member.pk])
        response = self.client.get(url)
        self.assertContains(response, 'No vacancy application exists for this team member.')
        self.assertNotIn('application', response.context['adminform'].form.fields)
        self.assertEqual(self.client.post(url, {
            'full_name': member.full_name, 'application': self.application.pk, '_save': 'Save',
        }).status_code, 302)
        member.refresh_from_db()
        self.application.refresh_from_db()
        self.assertIsNone(member.source_application_id)
        self.assertEqual(self.application.status, VacancyApplication.Status.OFFER_ACCEPTED)
