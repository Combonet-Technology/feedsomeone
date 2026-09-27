from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.forms.models import model_to_dict
from django.test import TestCase
from django.urls import reverse

from user.models import UserProfile

from .models import RecruitmentCohort, Vacancy, VacancyApplication
from .recruitment import submit_application


class RecruitmentCohortTests(TestCase):
    def setUp(self):
        self.cohort = RecruitmentCohort.objects.create(
            code='cohort-a', name='Cohort A', status=RecruitmentCohort.Status.OPEN,
        )
        self.vacancy = self.make_vacancy('writer-a', self.cohort)

    def make_vacancy(self, slug, cohort=None):
        return Vacancy.objects.create(
            cohort=cohort, title=slug, slug=slug,
            summary='Write for OEF', description='Write articles',
            expectations='Verify facts', responsibilities='Write',
            benefits='Experience', who_we_are_looking_for='A writer', status='open',
        )

    def apply(self, vacancy=None, email='writer@example.org', applicant=None):
        return submit_application(VacancyApplication(
            vacancy=vacancy or self.vacancy, full_name='Test Writer', email=email,
            applicant=applicant, cover_letter='Application', cv='test.pdf',
        ))

    def test_unbatched_intake_needs_no_cohort_or_legacy_flag(self):
        vacancy = self.make_vacancy('unbatched')
        self.assertTrue(vacancy.is_open)
        self.assertIsNone(self.apply(vacancy).cohort_id)
        self.assertEqual(RecruitmentCohort.objects.count(), 1)

    def test_closing_cohort_closes_only_linked_open_vacancies(self):
        application = self.apply()
        linked = self.make_vacancy('linked', self.cohort)
        unrelated = self.make_vacancy('unrelated')
        self.cohort.status = RecruitmentCohort.Status.INTAKE_CLOSED
        self.cohort.save()
        for vacancy in (self.vacancy, linked):
            vacancy.refresh_from_db()
            self.assertEqual(vacancy.status, 'closed')
            self.assertFalse(vacancy.is_open)
        unrelated.refresh_from_db()
        self.assertTrue(unrelated.is_open)
        application.refresh_from_db()
        self.assertEqual(application.status, VacancyApplication.Status.RECEIVED)
        self.assertEqual(application.cohort_id, self.cohort.pk)
        with self.assertRaises(ValidationError):
            self.apply(email='late@example.org')

    def test_vacancy_closure_does_not_close_its_cohort(self):
        self.vacancy.status = 'closed'
        self.vacancy.save()
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.status, RecruitmentCohort.Status.OPEN)

    def test_empty_cohort_stays_open_until_explicitly_closed(self):
        empty = RecruitmentCohort.objects.create(code='empty', name='Empty', status='open')
        empty.refresh_from_db()
        self.assertEqual(empty.status, 'open')
        empty.status = 'intake_closed'
        empty.save()

    def test_reopening_cohort_does_not_reopen_vacancies(self):
        self.cohort.status = 'completed'
        self.cohort.save()
        self.cohort.status = 'open'
        self.cohort.save()
        self.vacancy.refresh_from_db()
        self.assertEqual(self.vacancy.status, 'closed')
        self.vacancy.status = 'open'
        self.vacancy.save()
        self.assertTrue(self.vacancy.is_open)

    def test_reopened_vacancy_requires_unbatched_or_open_cohort(self):
        self.cohort.status = 'intake_closed'
        self.cohort.save()
        self.vacancy.refresh_from_db()
        self.vacancy.status = 'open'
        with self.assertRaises(ValidationError):
            self.vacancy.save()
        self.vacancy.cohort = None
        self.vacancy.save()
        self.assertTrue(self.vacancy.is_open)

    def test_returning_to_draft_does_not_allow_implicit_vacancy_reopening(self):
        self.cohort.status = 'draft'
        self.cohort.save(update_fields=('status',))
        self.cohort.status = 'open'
        self.cohort.save(update_fields=('status',))
        self.vacancy.refresh_from_db()
        self.assertEqual(self.vacancy.status, 'closed')
        self.assertFalse(self.vacancy.is_open)
        self.vacancy.status = 'open'
        self.vacancy.save()
        self.assertTrue(self.vacancy.is_open)

    def test_vacancy_reassignment_preserves_old_applications_and_allows_reapplication(self):
        first = self.apply()
        next_cohort = RecruitmentCohort.objects.create(code='next', name='Next', status='open')
        self.vacancy.cohort = next_cohort
        self.vacancy.save()
        second = self.apply()
        first.refresh_from_db()
        self.assertEqual(first.cohort_id, self.cohort.pk)
        self.assertEqual(second.cohort_id, next_cohort.pk)
        self.cohort.status = 'intake_closed'
        self.cohort.save()
        self.vacancy.refresh_from_db()
        self.assertTrue(self.vacancy.is_open)

    def test_same_batch_rejects_case_insensitive_duplicate_email(self):
        self.apply()
        with self.assertRaises(ValidationError):
            self.apply(email='WRITER@example.org')
        for cohort in (self.cohort, None):
            with self.subTest(cohort=cohort):
                if cohort is None:
                    VacancyApplication.objects.create(
                        vacancy=self.vacancy, email='writer@example.org', full_name='Unbatched',
                    )
                with self.assertRaises(IntegrityError), transaction.atomic():
                    VacancyApplication.objects.create(
                        vacancy=self.vacancy, cohort=cohort,
                        email='WRITER@example.org', full_name='Duplicate',
                    )

    def test_account_duplicate_is_scoped_to_current_cohort(self):
        user = UserProfile.objects.create_user(email='account@example.org')
        self.apply(applicant=user)
        with self.assertRaises(ValidationError):
            self.apply(email='another@example.org', applicant=user)
        self.vacancy.cohort = None
        self.vacancy.save()
        self.apply(applicant=user)
        with self.assertRaises(ValidationError):
            self.apply(email='another@example.org', applicant=user)

    def test_application_cohort_can_be_corrected_without_changing_outcome(self):
        application = self.apply()
        application.cohort = None
        application.save(update_fields=('cohort',))
        application.refresh_from_db()
        self.assertIsNone(application.cohort_id)
        self.assertEqual(application.status, 'received')

    def test_role_identity_still_freezes_after_first_application(self):
        self.apply()
        self.vacancy.title = 'Another role'
        with self.assertRaises(ValidationError):
            self.vacancy.save()

    def test_manager_admin_corrects_cohort_and_rejects_duplicate_correction(self):
        application = self.apply()
        manager = UserProfile.objects.create_user(
            email='manager@example.org', is_staff=True, is_active=True,
        )
        manager.groups.add(Group.objects.get(name='Recruitment Manager'))
        self.client.force_login(manager)
        url = reverse('admin:opportunities_vacancyapplication_change', args=(application.pk,))
        response = self.client.post(url, {'cohort': '', 'status': 'received', '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertIsNone(application.cohort_id)
        self.assertEqual(application.status, 'received')
        self.apply()
        response = self.client.post(url, {
            'cohort': self.cohort.pk, 'status': 'received', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['adminform'].form.errors)
        application.refresh_from_db()
        self.assertIsNone(application.cohort_id)
        self.assertEqual(application.status, 'received')

    def test_cohort_name_freezes_based_on_its_applications_not_current_vacancies(self):
        self.apply()
        self.vacancy.cohort = None
        self.vacancy.save()
        self.cohort.name = 'Renamed'
        with self.assertRaises(ValidationError):
            self.cohort.save()

    def test_vacancy_admin_renders_before_and_after_first_application(self):
        owner = UserProfile.objects.create_superuser(email='admin@example.org', password='test-password')
        self.client.force_login(owner)
        url = reverse('admin:opportunities_vacancy_change', args=(self.vacancy.pk,))
        editable = self.client.get(url)
        self.assertEqual(editable.status_code, 200)
        self.assertIn('slug', editable.context['adminform'].form.fields)
        self.apply()
        protected = self.client.get(url)
        self.assertEqual(protected.status_code, 200)
        self.assertNotIn('slug', protected.context['adminform'].form.fields)
        self.assertIn('cohort', protected.context['adminform'].form.fields)
        self.assertFalse(protected.context['adminform'].prepopulated_fields)
        data = model_to_dict(self.vacancy, fields=protected.context['adminform'].form.fields)
        data.update(cohort='', summary='Updated summary', _save='Save')
        data.pop('published_at', None)
        saved = self.client.post(url, data)
        self.assertEqual(saved.status_code, 302)
        self.vacancy.refresh_from_db()
        self.assertIsNone(self.vacancy.cohort_id)
        self.assertEqual(self.vacancy.summary, 'Updated summary')

    def test_migration_copies_only_known_cohort_mappings(self):
        known = VacancyApplication.objects.create(vacancy=self.vacancy, email='known@example.org')
        unbatched = self.make_vacancy('historical-unbatched')
        unknown = VacancyApplication.objects.create(vacancy=unbatched, email='unknown@example.org')
        migration = import_module('opportunities.migrations.0024_application_cohort_intake')
        migration.preserve_application_cohorts(apps, SimpleNamespace(connection=connection))
        known.refresh_from_db()
        unknown.refresh_from_db()
        self.assertEqual(known.cohort_id, self.cohort.pk)
        self.assertIsNone(unknown.cohort_id)

    def test_partial_cohort_save_does_not_close_vacancies_for_unsaved_status(self):
        self.cohort.status = 'intake_closed'
        self.cohort.name = 'New name'
        self.cohort.save(update_fields=('name',))
        self.vacancy.refresh_from_db()
        self.assertTrue(self.vacancy.is_open)
        self.cohort.save(update_fields=('status',))
        self.cohort.refresh_from_db()
        self.assertIsNotNone(self.cohort.intake_closed_at)
        self.vacancy.refresh_from_db()
        self.assertEqual(self.vacancy.status, 'closed')
