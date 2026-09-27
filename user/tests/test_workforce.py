from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from opportunities.models import Vacancy, VacancyApplication
from user.models import Engagement, TeamMember, UserProfile
from user.workforce import (appoint_candidate, complete_onboarding,
                            end_engagement, start_direct_engagement)


class WorkforceLifecycleTests(TestCase):
    def setUp(self):
        self.manager = UserProfile.objects.create_superuser(
            email='manager@example.org', password='test-password',
        )
        self.vacancy = Vacancy.objects.create(
            title='Content Writer', slug='content-writer-cohort-test',
            summary='Write for OEF', description='Write articles',
            expectations='Verify facts', responsibilities='Write',
            benefits='Experience', who_we_are_looking_for='A writer',
            status='open',
        )
        self.application = VacancyApplication.objects.create(
            vacancy=self.vacancy, full_name='Test Applicant',
            email='person@example.org', cover_letter='I would like to help.',
            cv='vacancy-applications/test.pdf',
            status=VacancyApplication.Status.ONBOARDING,
            agreement_verified_at=timezone.now(),
            agreement_verified_by=self.manager,
        )

    def test_appointment_creates_member_account_and_active_engagement_without_staff(self):
        engagement = appoint_candidate(self.application, self.manager)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.APPOINTED)
        self.assertEqual(self.application.applicant_id, engagement.team_member.user_id)
        self.assertEqual(engagement.status, Engagement.Status.ACTIVE)
        self.assertEqual(engagement.onboarding_status, Engagement.OnboardingStatus.NOT_STARTED)
        self.assertIsNone(engagement.onboarding_completed_at)
        self.assertIsNone(self.application.onboarding_completed_at)
        self.assertFalse(engagement.team_member.user.is_staff)
        self.assertFalse(engagement.team_member.user.has_usable_password())
        self.assertEqual(engagement.team_member.full_name, 'Test Applicant')
        self.assertEqual(appoint_candidate(self.application, self.manager).pk, engagement.pk)
        self.assertEqual(Engagement.objects.filter(source_application=self.application).count(), 1)

    def test_onboarding_completion_is_a_separate_recorded_action(self):
        engagement = appoint_candidate(self.application, self.manager)
        complete_onboarding(engagement, self.manager)
        engagement.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(engagement.onboarding_status, Engagement.OnboardingStatus.COMPLETED)
        self.assertIsNotNone(engagement.onboarding_completed_at)
        self.assertIsNotNone(self.application.onboarding_completed_at)

    def test_existing_engagement_without_verified_appointment_is_not_silently_certified(self):
        member = TeamMember.objects.create(
            full_name='Legacy member', primary_email='legacy@example.org',
        )
        Engagement.objects.create(
            team_member=member, source_application=self.application,
            role_title='Content Writer',
        )
        with self.assertRaisesMessage(ValidationError, 'Reconcile it explicitly'):
            appoint_candidate(self.application, self.manager)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.ONBOARDING)

    def test_appointment_does_not_require_intermediate_statuses(self):
        self.application.status = VacancyApplication.Status.OFFER_ACCEPTED
        self.application.agreement_verified_at = None
        self.application.agreement_verified_by = None
        self.application.save()
        engagement = appoint_candidate(self.application, self.manager)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.APPOINTED)
        self.assertIsNone(self.application.agreement_verified_at)
        self.assertEqual(engagement.status, Engagement.Status.ACTIVE)

    def test_direct_engagement_and_multiple_roles(self):
        member = TeamMember.objects.create(
            full_name='Direct Member', primary_email='direct@example.org',
            role_title='Programme Coordinator',
        )
        first = start_direct_engagement(
            member, self.manager, role_title='Programme Coordinator',
            engagement_type='volunteer',
        )
        second = start_direct_engagement(
            member, self.manager, role_title='Content Writer',
            engagement_type='volunteer',
        )
        self.assertNotEqual(first.pk, second.pk)
        member.refresh_from_db()
        self.assertEqual(member.engagements.count(), 2)
        self.assertFalse(member.user.is_staff)
        self.assertFalse(member.user.has_usable_password())
        self.assertEqual(end_engagement(first, self.manager).status, Engagement.Status.ENDED)

    def test_non_manager_cannot_appoint(self):
        user = UserProfile.objects.create_user(
            email='ordinary@example.org', password='test-password',
        )
        with self.assertRaises(PermissionDenied):
            appoint_candidate(self.application, user)

    def test_legacy_blank_member_is_hidden_until_verified_promotion(self):
        account = UserProfile.objects.create_user(
            email=self.application.email, password=None,
        )
        member = TeamMember.objects.create(
            user=account, source_application=self.application,
        )
        self.client.force_login(self.manager)
        url = reverse('admin:user_teammember_changelist')
        self.assertNotContains(self.client.get(url), 'Test Applicant')
        appoint_candidate(self.application, self.manager)
        response = self.client.get(url)
        self.assertContains(response, 'Test Applicant')
        member.refresh_from_db()
        self.assertEqual(member.full_name, 'Test Applicant')
        self.assertEqual(member.primary_email, self.application.email)

    def test_manual_team_member_creation_records_role_without_backend_access(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('admin:user_teammember_add'), {
            'full_name': 'Direct Recruit',
            'primary_email': 'direct-recruit@example.org',
            'role_title': 'Programme Coordinator',
            'engagement_type': 'volunteer',
            '_save': 'Save',
        })
        self.assertEqual(
            response.status_code, 302,
            response.context['adminform'].form.errors if response.context else '',
        )
        member = TeamMember.objects.get(primary_email='direct-recruit@example.org')
        engagement = member.engagements.get()
        self.assertEqual(engagement.role_title, 'Programme Coordinator')
        self.assertEqual(engagement.engagement_type, 'volunteer')
        self.assertEqual(engagement.onboarding_status, Engagement.OnboardingStatus.NOT_STARTED)
        self.assertFalse(member.user.is_staff)

    def test_engagement_admin_cannot_attach_role_to_unverified_legacy_member(self):
        legacy = TeamMember.objects.create(
            user=UserProfile.objects.create_user(email='legacy@example.org', password=None),
            source_application=self.application,
        )
        self.client.force_login(self.manager)
        response = self.client.post(reverse('admin:user_engagement_add'), {
            'team_member': legacy.pk,
            'role_title': 'Content Writer',
            'engagement_type': 'volunteer',
            '_save': 'Save',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Engagement.objects.filter(team_member=legacy).exists())

    def test_admin_status_transition_promotes_once(self):
        self.client.force_login(self.manager)
        url = reverse('admin:opportunities_vacancyapplication_change', args=(self.application.pk,))
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {
            'vacancy': self.vacancy.pk,
            'full_name': self.application.full_name,
            'email': self.application.email,
            'phone': '',
            'cover_letter': self.application.cover_letter,
            'status': VacancyApplication.Status.APPOINTED,
            '_save': 'Save',
        }
        response = self.client.post(url, data)
        self.assertEqual(
            response.status_code, 302,
            response.context['adminform'].form.errors if response.context else '',
        )
        self.assertEqual(Engagement.objects.filter(source_application=self.application).count(), 1)
        self.assertEqual(TeamMember.objects.count(), 1)

    def test_admin_can_appoint_without_intermediate_statuses(self):
        self.application.status = VacancyApplication.Status.AGREEMENT_SIGNED
        self.application.save(update_fields=('status',))
        self.client.force_login(self.manager)
        url = reverse('admin:opportunities_vacancyapplication_change', args=(self.application.pk,))
        response = self.client.post(url, {
            'vacancy': self.vacancy.pk,
            'full_name': self.application.full_name,
            'email': self.application.email,
            'phone': '',
            'cover_letter': self.application.cover_letter,
            'status': VacancyApplication.Status.APPOINTED,
            '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Engagement.objects.filter(source_application=self.application).exists())

    def test_admin_can_assign_legacy_active_status(self):
        self.application.status = VacancyApplication.Status.OFFER_ACCEPTED
        self.application.save(update_fields=('status',))
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('admin:opportunities_vacancyapplication_change', args=(self.application.pk,)),
            {
                'vacancy': self.vacancy.pk,
                'full_name': self.application.full_name,
                'email': self.application.email,
                'phone': '',
                'cover_letter': self.application.cover_letter,
                'status': VacancyApplication.Status.ACTIVE,
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.ACTIVE)
        self.assertFalse(Engagement.objects.filter(source_application=self.application).exists())

    def test_admin_can_change_declined_agreement_to_onboarding(self):
        self.application.status = VacancyApplication.Status.AGREEMENT_DECLINED
        self.application.save(update_fields=('status',))
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('admin:opportunities_vacancyapplication_change', args=(self.application.pk,)),
            {
                'vacancy': self.vacancy.pk,
                'full_name': self.application.full_name,
                'email': self.application.email,
                'phone': '',
                'cover_letter': self.application.cover_letter,
                'status': VacancyApplication.Status.ONBOARDING,
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.ONBOARDING)

    def test_admin_verified_signed_agreement_can_enter_onboarding(self):
        self.application.status = VacancyApplication.Status.AGREEMENT_SIGNED
        self.application.save(update_fields=('status',))
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('admin:opportunities_vacancyapplication_change', args=(self.application.pk,)),
            {
                'vacancy': self.vacancy.pk,
                'full_name': self.application.full_name,
                'email': self.application.email,
                'phone': '',
                'cover_letter': self.application.cover_letter,
                'status': VacancyApplication.Status.ONBOARDING,
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.ONBOARDING)

    def test_status_correction_after_appointment_preserves_membership_and_access(self):
        engagement = appoint_candidate(self.application, self.manager)
        account = engagement.team_member.user
        writer_group, _ = Group.objects.get_or_create(name='OEF Writers')
        account.groups.add(writer_group)
        account.is_staff = True
        account.save(update_fields=('is_staff',))
        self.application.status = VacancyApplication.Status.REVIEWING
        self.application.save(update_fields=('status',))
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.REVIEWING)
        self.assertTrue(TeamMember.objects.filter(pk=engagement.team_member_id).exists())
        self.assertEqual(appoint_candidate(self.application, self.manager).pk, engagement.pk)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.APPOINTED)
        self.assertEqual(Engagement.objects.filter(source_application=self.application).count(), 1)
        account.refresh_from_db()
        self.assertTrue(account.is_staff)
        self.assertTrue(account.groups.filter(pk=writer_group.pk).exists())

    def test_admin_saves_other_changes_when_directly_appointing(self):
        self.application.status = VacancyApplication.Status.RECEIVED
        self.application.agreement_verified_at = None
        self.application.agreement_verified_by = None
        self.application.save()
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('admin:opportunities_vacancyapplication_change', args=(self.application.pk,)),
            {
                'vacancy': self.vacancy.pk,
                'full_name': 'Corrected Applicant',
                'email': self.application.email,
                'phone': '',
                'cover_letter': self.application.cover_letter,
                'status': VacancyApplication.Status.APPOINTED,
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.full_name, 'Corrected Applicant')
        self.assertEqual(self.application.engagement.team_member.full_name, 'Corrected Applicant')

    def test_admin_identity_conflict_is_a_form_error(self):
        UserProfile.objects.create_user(email=self.application.email, password=None)
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('admin:opportunities_vacancyapplication_change', args=(self.application.pk,)),
            {
                'vacancy': self.vacancy.pk,
                'full_name': self.application.full_name,
                'email': self.application.email,
                'phone': '',
                'cover_letter': self.application.cover_letter,
                'status': VacancyApplication.Status.APPOINTED,
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An account with this email exists')
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, VacancyApplication.Status.ONBOARDING)
        self.assertFalse(Engagement.objects.filter(source_application=self.application).exists())
