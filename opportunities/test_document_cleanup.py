from unittest.mock import patch

from django.test import TestCase

from opportunities.models import (PrivateDocumentDeletion, Vacancy,
                                  VacancyApplication, VolunteerOffer)


class ApplicantCVDeletionTests(TestCase):
    def setUp(self):
        self.vacancy = Vacancy.objects.create(
            title='Writer', slug='writer', summary='Summary', description='Description',
            expectations='Expectations', responsibilities='Responsibilities',
            benefits='Benefits', who_we_are_looking_for='Writers',
        )

    @patch('opportunities.document_cleanup.VacancyPrivateDocumentStorage.delete')
    def test_hard_deleting_application_deletes_cv_after_commit(self, storage_delete):
        application = VacancyApplication.objects.create(
            vacancy=self.vacancy, full_name='Test Writer', email='writer@example.com',
            cv='oef/test/vacancy-applications/private-cv/example.pdf', cover_letter='Letter',
        )
        with self.captureOnCommitCallbacks(execute=True):
            application.delete()

        storage_delete.assert_called_once_with('oef/test/vacancy-applications/private-cv/example.pdf')
        task = PrivateDocumentDeletion.objects.get()
        self.assertEqual(task.status, PrivateDocumentDeletion.Status.COMPLETED)
        self.assertEqual(task.attempts, 1)

    @patch(
        'opportunities.document_cleanup.VacancyPrivateDocumentStorage.delete',
        side_effect=RuntimeError('provider unavailable'),
    )
    def test_failed_provider_delete_remains_pending_for_retry(self, storage_delete):
        application = VacancyApplication.objects.create(
            vacancy=self.vacancy, full_name='Retry Writer', email='retry@example.com',
            cv='oef/test/vacancy-applications/private-cv/retry.pdf', cover_letter='Letter',
        )
        with self.captureOnCommitCallbacks(execute=True):
            application.delete()

        task = PrivateDocumentDeletion.objects.get()
        self.assertEqual(task.status, PrivateDocumentDeletion.Status.PENDING)
        self.assertEqual(task.attempts, 1)
        self.assertIn('provider unavailable', task.last_error)

    @patch('opportunities.document_cleanup.VacancyPrivateDocumentStorage.delete')
    def test_deleting_offer_deletes_generated_pdf_after_commit(self, storage_delete):
        application = VacancyApplication.objects.create(
            vacancy=self.vacancy, full_name='Offer Recipient', email='offer@example.com',
            cv='', cover_letter='Letter',
        )
        offer = VolunteerOffer.objects.create(
            application=application, recipient_name='Offer Recipient',
            recipient_email='offer@example.com', role_title='Writer',
            letter_date='2026-08-25', start_date='2026-09-01',
            initial_period='Three months', weekly_commitment='Ten hours',
            work_arrangement='Remote', reporting_contact='OEF',
            role_contribution='Writing',
            letter_pdf='oef/test/volunteer-offers/private/offer.pdf',
        )

        with self.captureOnCommitCallbacks(execute=True):
            offer.delete()

        storage_delete.assert_called_once_with(
            'oef/test/volunteer-offers/private/offer.pdf'
        )
