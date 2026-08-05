from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ext_libs.email_service import (EmailProviderError,
                                    send_template_email_batch)
from user.models import UserProfile

from .admin import VacancyApplicationAdmin
from .models import Vacancy, VacancyApplication
from .rejections import RejectionBatchResult, send_rejection_email_batch


def create_application(vacancy, identifier, status='not_selected'):
    return VacancyApplication.objects.create(
        vacancy=vacancy,
        full_name=f'Adaeze {identifier}',
        email=f'adaeze-{identifier}@example.com',
        cv=f'vacancy_applications/private_cv/{identifier}.pdf',
        cover_letter='I would like to contribute.',
        status=status,
    )


class BrevoRejectionBatchPayloadTests(TestCase):
    @override_settings(
        BREVO_API_KEY='test-key',
        BREVO_API_BASE_URL='https://api.brevo.test/v3',
        BREVO_TIMEOUT_SECONDS=10,
    )
    @patch('ext_libs.email_service.requests.post')
    def test_batch_payload_uses_versions_and_idempotency_key(self, post):
        response = Mock(status_code=201)
        response.json.return_value = {'messageIds': ['message-1', 'message-2']}
        post.return_value = response
        versions = [
            {'to': [{'email': 'one@example.com'}], 'params': {'first_name': 'One'}},
            {'to': [{'email': 'two@example.com'}], 'params': {'first_name': 'Two'}},
        ]

        result = send_template_email_batch(versions, 7, 'batch-key')

        self.assertEqual(result, ['message-1', 'message-2'])
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['templateId'], 7)
        self.assertEqual(payload['messageVersions'], versions)
        self.assertEqual(payload['headers']['idempotencyKey'], 'batch-key')

    @override_settings(
        BREVO_API_KEY='test-key',
        BREVO_API_BASE_URL='https://api.brevo.test/v3',
        BREVO_TIMEOUT_SECONDS=10,
    )
    @patch('ext_libs.email_service.requests.post')
    def test_batch_response_requires_one_message_id_per_version(self, post):
        response = Mock(status_code=201)
        response.json.return_value = {'messageIds': ['message-1']}
        post.return_value = response

        with self.assertRaises(EmailProviderError):
            send_template_email_batch(
                [
                    {'to': [{'email': 'one@example.com'}]},
                    {'to': [{'email': 'two@example.com'}]},
                ],
                7,
                'batch-key',
            )


@override_settings(
    BREVO_REJECTION_TEMPLATE_ID=7,
    OEF_INSTAGRAM_URL='https://social.example/instagram',
    OEF_LINKEDIN_URL='https://social.example/linkedin',
    OEF_X_URL='https://social.example/x',
    OEF_YOUTUBE_URL='https://social.example/youtube',
)
class RejectionEmailWorkflowTests(TestCase):
    def setUp(self):
        self.owner = UserProfile.objects.create_superuser(
            email='owner@example.com',
            password='owner-test-password',
        )
        self.vacancy = Vacancy.objects.create(
            title='Volunteer Programme Coordinator',
            slug='programme-coordinator-rejection-test',
            summary='Coordinate programme delivery.',
            description='Support OEF programme coordination.',
            expectations='Work collaboratively.',
            responsibilities='Coordinate programme activities.',
            benefits='Practical nonprofit experience.',
            who_we_are_looking_for='An organised coordinator.',
            engagement_type='volunteer',
            status='closed',
        )

    @patch(
        'opportunities.rejections.send_template_email_batch',
        return_value=['brevo-rejection-1'],
    )
    def test_batch_sends_only_unsent_not_selected_applications(self, send_batch):
        eligible = create_application(self.vacancy, 'eligible')
        create_application(self.vacancy, 'reviewing', status='reviewing')
        already_sent = create_application(self.vacancy, 'sent')
        already_sent.rejection_email_status = 'sent'
        already_sent.rejection_email_sent_at = timezone.now()
        already_sent.save()

        result = send_rejection_email_batch(
            VacancyApplication.objects.all(),
            self.owner,
        )

        self.assertEqual(result.sent, 1)
        self.assertEqual(result.skipped_wrong_status, 1)
        self.assertEqual(result.skipped_already_sent, 1)
        eligible.refresh_from_db()
        self.assertEqual(eligible.rejection_email_status, 'sent')
        self.assertEqual(eligible.rejection_email_message_id, 'brevo-rejection-1')
        self.assertEqual(eligible.rejection_email_sent_by, self.owner)
        version = send_batch.call_args.kwargs['message_versions'][0]
        self.assertEqual(version['params']['first_name'], 'Adaeze')
        self.assertEqual(
            version['params']['role_title'],
            'Volunteer Programme Coordinator',
        )
        self.assertEqual(
            version['params']['linkedin_url'],
            'https://social.example/linkedin',
        )
        self.assertEqual(
            version['params']['instagram_url'],
            'https://social.example/instagram',
        )
        self.assertEqual(version['params']['x_url'], 'https://social.example/x')

    @patch(
        'opportunities.rejections.send_template_email_batch',
        side_effect=EmailProviderError('Brevo unavailable'),
    )
    def test_provider_failure_is_recorded_and_can_be_retried(self, send_batch):
        application = create_application(self.vacancy, 'failed')

        result = send_rejection_email_batch(
            VacancyApplication.objects.filter(pk=application.pk),
            self.owner,
        )

        self.assertEqual(result.failed, 1)
        application.refresh_from_db()
        self.assertEqual(application.rejection_email_status, 'failed')
        self.assertIsNone(application.rejection_email_sent_at)
        self.assertIn('Brevo unavailable', application.rejection_email_error)


class RejectionEmailAdminTests(TestCase):
    def setUp(self):
        self.manager = UserProfile.objects.create_user(
            email='recruitment@example.com',
            password='manager-test-password',
            is_active=True,
            is_staff=True,
        )
        self.manager.groups.add(Group.objects.get(name='Recruitment Manager'))
        self.outsider = UserProfile.objects.create_user(
            email='outsider@example.com',
            password='outsider-test-password',
            is_active=True,
            is_staff=True,
        )
        self.vacancy = Vacancy.objects.create(
            title='Volunteer Programme Coordinator',
            slug='programme-coordinator-rejection-admin-test',
            summary='Coordinate programme delivery.',
            description='Support OEF programme coordination.',
            expectations='Work collaboratively.',
            responsibilities='Coordinate programme activities.',
            benefits='Practical nonprofit experience.',
            who_we_are_looking_for='An organised coordinator.',
            engagement_type='volunteer',
            status='closed',
        )
        self.application = create_application(self.vacancy, 'admin')
        self.changelist_url = reverse(
            'admin:opportunities_vacancyapplication_changelist'
        )

    def test_bulk_action_is_only_available_with_rejection_permission(self):
        model_admin = VacancyApplicationAdmin(VacancyApplication, admin.site)
        request = RequestFactory().get(self.changelist_url)
        request.user = self.manager
        manager_actions = model_admin.get_actions(request)
        request.user = self.outsider
        outsider_actions = model_admin.get_actions(request)

        self.assertIn('send_rejection_emails', manager_actions)
        self.assertNotIn('send_rejection_emails', outsider_actions)

    @patch('opportunities.admin.send_rejection_email_batch')
    def test_confirmation_is_required_before_bulk_send(self, send_batch):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.changelist_url,
            {
                'action': 'send_rejection_emails',
                '_selected_action': [str(self.application.pk)],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirm rejection email send')
        self.assertContains(response, 'will receive the active OEF rejection email')
        send_batch.assert_not_called()

    @patch('opportunities.admin.send_rejection_email_batch')
    def test_confirmed_bulk_send_calls_service(self, send_batch):
        send_batch.return_value = RejectionBatchResult(requested=1, sent=1)
        self.client.force_login(self.manager)

        response = self.client.post(
            self.changelist_url,
            {
                'action': 'send_rejection_emails',
                '_selected_action': [str(self.application.pk)],
                'confirm_rejection_send': '1',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        send_batch.assert_called_once()
        self.assertEqual(send_batch.call_args.args[1], self.manager)
        self.assertContains(response, 'Rejection email batch complete: 1 sent')
