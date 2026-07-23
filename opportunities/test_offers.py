import base64
import tempfile
from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from ext_libs.email_service import EmailProviderError, send_email
from user.models import UserProfile

from .models import Vacancy, VacancyApplication, VolunteerOffer
from .offers import OfferAlreadySent, render_offer_pdf, send_volunteer_offer


class BrevoAttachmentTests(TestCase):
    @override_settings(
        BREVO_API_KEY='test-key',
        BREVO_API_BASE_URL='https://api.brevo.test/v3',
        BREVO_SENDER_EMAIL='no-reply@example.org',
        BREVO_SENDER_NAME='OEF',
        BREVO_REPLY_TO_EMAIL='info@example.org',
        BREVO_TIMEOUT_SECONDS=10,
    )
    @patch('ext_libs.email_service.requests.post')
    def test_send_email_encodes_pdf_attachment_and_returns_message_id(self, mock_post):
        response = Mock(status_code=201)
        response.json.return_value = {'messageId': 'brevo-message-123'}
        mock_post.return_value = response

        result = send_email(
            destination='volunteer@example.com',
            subject='Offer',
            content='<p>Your offer is attached.</p>',
            text_content='Your offer is attached.',
            attachments=({'name': 'offer.pdf', 'content': b'%PDF-test'},),
            message_headers={'Idempotency-Key': 'offer-key'},
        )

        self.assertEqual(result, 'brevo-message-123')
        payload = mock_post.call_args.kwargs['json']
        self.assertEqual(
            payload['attachment'],
            [
                {
                    'name': 'offer.pdf',
                    'content': base64.b64encode(b'%PDF-test').decode('ascii'),
                }
            ],
        )
        self.assertEqual(payload['headers']['Idempotency-Key'], 'offer-key')
        self.assertEqual(payload['textContent'], 'Your offer is attached.')


@override_settings(CLOUDINARY_STORAGE={})
class VolunteerOfferWorkflowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_directory = tempfile.TemporaryDirectory()
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_directory.name)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        cls.media_directory.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.vacancy = Vacancy.objects.create(
            title='Volunteer Grant and Research Writer',
            slug='grant-research-writer-offer-test',
            team='Grants and Research',
            summary='Research suitable funding opportunities and support grant applications.',
            description='Support OEF grant readiness.',
            expectations='Communicate reliably.',
            responsibilities='Research grants.',
            benefits='Build practical experience.',
            who_we_are_looking_for='A careful researcher.',
            work_mode='remote',
            location='Nigeria',
            time_commitment='10 hours per week',
            status='open',
        )
        self.application = VacancyApplication.objects.create(
            vacancy=self.vacancy,
            full_name='Temitope Florence Ademiju',
            email='florence@example.com',
            cv='vacancy_applications/private_cv/florence.pdf',
            cover_letter='I would like to contribute.',
            status='shortlisted',
        )
        self.sender = UserProfile.objects.create_superuser(
            email='hr@example.com',
            password='test-password',
        )
        self.form_data = {
            'start_date': date(2026, 7, 23),
            'initial_period': 'Three months',
            'weekly_commitment': '10 hours per week',
            'work_arrangement': (
                'Remote, with hours arranged flexibly around agreed priorities and deadlines'
            ),
            'reporting_contact': 'Olanrewaju Oluwafemi Ebenezer, Founder and Trustee',
            'role_contribution': (
                'Research suitable funding opportunities and support clear, evidence-based '
                'grant applications.'
            ),
            'acceptance_deadline': None,
            'confirm_send': True,
        }

    @patch('opportunities.offers.send_email', return_value='brevo-message-123')
    @patch('opportunities.offers.render_offer_pdf', return_value=b'%PDF-test-offer')
    def test_service_sends_and_records_offer(self, mock_render_pdf, mock_send_email):
        offer = send_volunteer_offer(self.application, self.form_data, self.sender)

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'offered')
        self.assertEqual(offer.delivery_status, 'sent')
        self.assertEqual(offer.brevo_message_id, 'brevo-message-123')
        self.assertEqual(offer.sent_by, self.sender)
        self.assertIsNotNone(offer.sent_at)
        self.assertTrue(offer.letter_pdf.name.startswith('vacancy_applications/private_offers/'))
        with offer.letter_pdf.open('rb') as letter:
            self.assertEqual(letter.read(), b'%PDF-test-offer')

        email_kwargs = mock_send_email.call_args.kwargs
        self.assertEqual(email_kwargs['destination'], 'florence@example.com')
        self.assertEqual(email_kwargs['attachments'][0]['content'], b'%PDF-test-offer')
        self.assertIn('selected for the role', email_kwargs['content'])
        self.assertNotIn('10 hours per week', email_kwargs['content'])
        mock_render_pdf.assert_called_once()

    @patch(
        'opportunities.offers.send_email',
        side_effect=EmailProviderError('Brevo unavailable'),
    )
    @patch('opportunities.offers.render_offer_pdf', return_value=b'%PDF-test-offer')
    def test_delivery_failure_is_recorded_without_changing_application_status(
        self,
        mock_render_pdf,
        mock_send_email,
    ):
        with self.assertRaises(EmailProviderError):
            send_volunteer_offer(self.application, self.form_data, self.sender)

        self.application.refresh_from_db()
        offer = VolunteerOffer.objects.get(application=self.application)
        self.assertEqual(self.application.status, 'shortlisted')
        self.assertEqual(offer.delivery_status, 'failed')
        self.assertIn('Brevo unavailable', offer.delivery_error)
        self.assertIsNone(offer.sent_at)

    @patch('opportunities.offers.send_email', return_value='brevo-message-123')
    @patch('opportunities.offers.render_offer_pdf', return_value=b'%PDF-test-offer')
    def test_sent_offer_cannot_be_sent_again(self, mock_render_pdf, mock_send_email):
        send_volunteer_offer(self.application, self.form_data, self.sender)

        with self.assertRaises(OfferAlreadySent):
            send_volunteer_offer(self.application, self.form_data, self.sender)

        mock_send_email.assert_called_once()

    def test_admin_offer_screen_requires_send_permission(self):
        staff = UserProfile.objects.create_user(
            email='staff@example.com',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(
            reverse(
                'admin:opportunities_vacancyapplication_send_offer',
                args=(self.application.pk,),
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_offer_screen_prefills_reusable_terms(self):
        self.client.force_login(self.sender)

        response = self.client.get(
            reverse(
                'admin:opportunities_vacancyapplication_send_offer',
                args=(self.application.pk,),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.application.full_name)
        self.assertContains(response, self.application.email)
        self.assertContains(response, self.vacancy.title)
        self.assertContains(response, '10 hours per week')
        self.assertContains(response, 'Generate and send offer')

    def test_real_pdf_renderer_produces_a_pdf_document(self):
        offer = VolunteerOffer(
            application=self.application,
            recipient_name=self.application.full_name,
            recipient_email=self.application.email,
            role_title=self.vacancy.title,
            letter_date=date(2026, 7, 23),
            start_date=date(2026, 7, 23),
            initial_period='Three months',
            weekly_commitment='10 hours per week',
            work_arrangement='Remote',
            reporting_contact='OEF Founder and Trustee',
            role_contribution='Support credible grant applications.',
        )

        pdf = render_offer_pdf(offer)

        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 10_000)

    @patch('opportunities.admin.send_volunteer_offer')
    def test_admin_requires_explicit_confirmation_before_sending(self, mock_send_offer):
        self.client.force_login(self.sender)
        post_data = {
            'start_date': '2026-07-23',
            'initial_period': 'Three months',
            'weekly_commitment': '10 hours per week',
            'work_arrangement': 'Remote',
            'reporting_contact': 'OEF Founder and Trustee',
            'role_contribution': 'Support credible grant applications.',
            'acceptance_deadline': '',
        }

        response = self.client.post(
            reverse(
                'admin:opportunities_vacancyapplication_send_offer',
                args=(self.application.pk,),
            ),
            post_data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required.')
        mock_send_offer.assert_not_called()
