from unittest.mock import Mock, patch

from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from ext_libs.email_service import EmailProviderError, send_template_email
from user.models import UserProfile

from .models import Vacancy, VacancyApplication, VolunteerOnboarding
from .onboarding import (OnboardingEmailNotEligible,
                         OnboardingEmailStateChanged, send_onboarding_email)


def create_onboarding_application(slug):
    vacancy = Vacancy.objects.create(
        title='Volunteer Programme Coordinator',
        slug=slug,
        summary='Coordinate programme delivery.',
        description='Support OEF programme coordination.',
        expectations='Work collaboratively.',
        responsibilities='Coordinate programme activities.',
        benefits='Practical nonprofit experience.',
        who_we_are_looking_for='An organised coordinator.',
        engagement_type='volunteer',
        status='open',
    )
    return VacancyApplication.objects.create(
        vacancy=vacancy,
        full_name='Adaeze Okafor',
        email='adaeze@example.com',
        cv='vacancy_applications/private_cv/adaeze.pdf',
        cover_letter='I would like to contribute.',
        status='onboarding',
    )


class BrevoOnboardingTemplatePayloadTests(TestCase):
    @override_settings(
        BREVO_API_KEY='test-key',
        BREVO_API_BASE_URL='https://api.brevo.test/v3',
        BREVO_TIMEOUT_SECONDS=10,
    )
    @patch('ext_libs.email_service.requests.post')
    def test_template_sender_forwards_idempotency_header_and_message_id(self, post):
        response = Mock(status_code=201)
        response.json.return_value = {'messageId': 'brevo-onboarding-1'}
        post.return_value = response

        result = send_template_email(
            destination='volunteer@example.com',
            template_id=2,
            params={'first_name': 'Adaeze'},
            message_headers={'Idempotency-Key': 'delivery-key'},
        )

        self.assertEqual(result, 'brevo-onboarding-1')
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['headers']['Idempotency-Key'], 'delivery-key')
        self.assertEqual(payload['templateId'], 2)


@override_settings(
    BREVO_ONBOARDING_TEMPLATE_ID=2,
    OEF_SLACK_INVITE_URL='https://join.slack.test/oef',
)
class VolunteerOnboardingWorkflowTests(TestCase):
    def setUp(self):
        self.owner = UserProfile.objects.create_superuser(
            email='owner@example.com',
            password='owner-test-password',
        )
        self.application = create_onboarding_application(
            'programme-coordinator-onboarding-test'
        )

    @patch(
        'opportunities.onboarding.send_template_email',
        return_value='brevo-onboarding-1',
    )
    def test_first_send_records_permanent_delivery_history(self, send_template_email):
        onboarding = send_onboarding_email(self.application, self.owner, 0)

        self.assertEqual(onboarding.delivery_status, 'sent')
        self.assertEqual(onboarding.send_count, 1)
        self.assertIsNotNone(onboarding.first_sent_at)
        self.assertEqual(onboarding.first_sent_at, onboarding.last_sent_at)
        self.assertEqual(onboarding.last_sent_by, self.owner)
        self.assertEqual(onboarding.brevo_message_id, 'brevo-onboarding-1')
        kwargs = send_template_email.call_args.kwargs
        self.assertEqual(kwargs['destination'], 'adaeze@example.com')
        self.assertEqual(kwargs['template_id'], 2)
        self.assertEqual(kwargs['params']['first_name'], 'Adaeze')
        self.assertEqual(
            kwargs['params']['slack_invite_url'],
            'https://join.slack.test/oef',
        )
        self.assertIn('Idempotency-Key', kwargs['message_headers'])

    @patch(
        'opportunities.onboarding.send_template_email',
        side_effect=('brevo-onboarding-1', 'brevo-onboarding-2'),
    )
    def test_confirmed_resend_preserves_first_send_and_increments_count(
        self,
        send_template_email,
    ):
        first = send_onboarding_email(self.application, self.owner, 0)
        first_sent_at = first.first_sent_at
        first_delivery_key = first.delivery_key

        resent = send_onboarding_email(self.application, self.owner, 1)

        self.assertEqual(resent.send_count, 2)
        self.assertEqual(resent.first_sent_at, first_sent_at)
        self.assertGreaterEqual(resent.last_sent_at, first_sent_at)
        self.assertNotEqual(resent.delivery_key, first_delivery_key)
        self.assertEqual(send_template_email.call_count, 2)

    @patch(
        'opportunities.onboarding.send_template_email',
        return_value='brevo-onboarding-1',
    )
    def test_stale_confirmation_cannot_send_a_duplicate(self, send_template_email):
        send_onboarding_email(self.application, self.owner, 0)

        with self.assertRaises(OnboardingEmailStateChanged):
            send_onboarding_email(self.application, self.owner, 0)

        self.assertEqual(send_template_email.call_count, 1)

    def test_application_must_be_in_onboarding_or_active_status(self):
        self.application.status = 'agreement_signed'
        self.application.save(update_fields=('status', 'updated_at'))

        with self.assertRaises(OnboardingEmailNotEligible):
            send_onboarding_email(self.application, self.owner, 0)

        self.assertFalse(
            VolunteerOnboarding.objects.filter(application=self.application).exists()
        )

    @patch(
        'opportunities.onboarding.send_template_email',
        side_effect=EmailProviderError('Brevo unavailable'),
    )
    def test_delivery_failure_is_recorded_without_marking_email_sent(
        self,
        send_template_email,
    ):
        with self.assertRaises(EmailProviderError):
            send_onboarding_email(self.application, self.owner, 0)

        onboarding = VolunteerOnboarding.objects.get(application=self.application)
        self.assertEqual(onboarding.delivery_status, 'failed')
        self.assertEqual(onboarding.send_count, 0)
        self.assertIsNone(onboarding.first_sent_at)
        self.assertIn('Brevo unavailable', onboarding.delivery_error)


@override_settings(
    BREVO_ONBOARDING_TEMPLATE_ID=2,
    OEF_SLACK_INVITE_URL='https://join.slack.test/oef',
)
class VolunteerOnboardingAdminTests(TestCase):
    def setUp(self):
        self.onboarding_group = Group.objects.get(name='Volunteer Onboarding')
        self.recruitment_group = Group.objects.get(name='Recruitment Manager')
        self.manager = UserProfile.objects.create_user(
            email='onboarding@example.com',
            password='manager-test-password',
            is_active=True,
            is_staff=True,
        )
        self.manager.groups.add(self.onboarding_group)
        self.outsider = UserProfile.objects.create_user(
            email='recruitment@example.com',
            password='recruitment-test-password',
            is_active=True,
            is_staff=True,
        )
        self.outsider.groups.add(self.recruitment_group)
        self.application = create_onboarding_application(
            'programme-coordinator-onboarding-admin-test'
        )
        self.change_url = reverse(
            'admin:opportunities_vacancyapplication_change',
            args=(self.application.pk,),
        )
        self.send_url = reverse(
            'admin:opportunities_vacancyapplication_send_onboarding',
            args=(self.application.pk,),
        )

    def test_authorised_manager_sees_start_onboarding_action(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.change_url)

        self.assertContains(response, 'Start onboarding')
        self.assertContains(response, self.send_url)
        self.assertNotContains(
            response,
            'You do not have permission to start volunteer onboarding.',
        )

    def test_recruitment_manager_without_permission_sees_disabled_action(self):
        self.client.force_login(self.outsider)

        response = self.client.get(self.change_url)

        self.assertContains(response, 'Start onboarding')
        self.assertContains(
            response,
            'You do not have permission to start volunteer onboarding.',
        )
        self.assertNotContains(response, f'href="{self.send_url}"')

    def test_action_is_disabled_until_application_enters_onboarding(self):
        self.application.status = 'agreement_signed'
        self.application.save(update_fields=('status', 'updated_at'))
        self.client.force_login(self.manager)

        response = self.client.get(self.change_url)

        self.assertContains(
            response,
            'Set the application status to Onboarding before starting onboarding.',
        )
        self.assertNotContains(response, f'href="{self.send_url}"')

    def test_direct_action_access_requires_onboarding_permission(self):
        self.client.force_login(self.outsider)

        response = self.client.get(self.send_url)

        self.assertEqual(response.status_code, 403)

    @patch(
        'opportunities.admin.send_onboarding_email',
    )
    def test_confirmation_is_required_before_sending(self, send_onboarding_email):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.send_url,
            {'expected_send_count': '0'},
        )

        self.assertEqual(response.status_code, 200)
        send_onboarding_email.assert_not_called()

    @patch(
        'opportunities.admin.send_onboarding_email',
    )
    def test_authorised_manager_can_start_onboarding(self, send_onboarding_email):
        send_onboarding_email.return_value = VolunteerOnboarding(
            application=self.application,
            send_count=1,
        )
        self.client.force_login(self.manager)

        response = self.client.post(
            self.send_url,
            {'expected_send_count': '0', 'confirm_send': 'on'},
        )

        self.assertRedirects(response, self.change_url)
        send_onboarding_email.assert_called_once_with(
            self.application,
            self.manager,
            0,
        )

    def test_sent_email_changes_action_to_resend_with_warning(self):
        VolunteerOnboarding.objects.create(
            application=self.application,
            delivery_status='sent',
            send_count=1,
            first_sent_at='2026-08-04T08:00:00Z',
            last_sent_at='2026-08-04T08:00:00Z',
            last_sent_by=self.manager,
        )
        self.client.force_login(self.manager)

        change_response = self.client.get(self.change_url)
        confirmation_response = self.client.get(self.send_url)

        self.assertContains(change_response, 'Resend onboarding email')
        self.assertNotContains(change_response, '>Start onboarding<')
        self.assertContains(
            confirmation_response,
            'This onboarding email has already been sent 1',
        )
        self.assertContains(confirmation_response, 'time.')
        self.assertContains(
            confirmation_response,
            'I understand that this volunteer has already received',
        )
