import tempfile
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from user.models import UserProfile

from .models import Vacancy, VacancyApplication
from .notifications import notify_new_application
from .storage import AuthenticatedRawCloudinaryStorage, VacancyCVStorage


def catalogue_markdown(version=3, writer_summary='Write useful stories.'):
    catalogue = dedent(
        '''
        # Test Vacancy Catalogue

        ```yaml
        catalogue_version: __VERSION__
        defaults:
          about_oef: OEF supports underserved communities.
          engagement_type: volunteer
          work_mode: remote
          location: Nigeria
          is_active: true
        vacancies:
          - slug: test-writer
            title: Test Writer
            team: Communications
            summary: __WRITER_SUMMARY__
            description: Write programme content.
            who_we_are_looking_for: A thoughtful writer.
            responsibilities: Write and edit.
            expectations: Communicate reliably.
            benefits: Gain editorial experience.
            time_commitment: 4 hours per week
            status: open
            positions_available: 5
            display_order: 10
          - slug: test-designer
            title: Test Designer
            team: Communications
            summary: Design useful materials.
            description: Design programme assets.
            who_we_are_looking_for: A thoughtful designer.
            responsibilities: Design and export assets.
            expectations: Communicate reliably.
            benefits: Gain design experience.
            time_commitment: Flexible
            status: filled
            positions_available: 1
            display_order: 20
        ```
        '''
    ).strip()
    return catalogue.replace('__VERSION__', str(version)).replace(
        '__WRITER_SUMMARY__',
        writer_summary,
    )


class VacancyApplicationTests(TestCase):
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
        self.notification_patcher = patch(
            'opportunities.views.notify_new_application',
        )
        self.mock_notify_new_application = self.notification_patcher.start()
        self.addCleanup(self.notification_patcher.stop)
        self.vacancy = Vacancy.objects.create(
            title='Volunteer Writer',
            slug='volunteer-writer',
            team='Communications and Storytelling',
            summary='Write useful stories.',
            about_oef='OEF supports underserved communities.',
            description='Help us tell impact stories.',
            expectations='Reliable communication.\nMeet agreed deadlines.',
            responsibilities='Write articles.\nEdit programme updates.',
            benefits='Portfolio experience.\nEditorial feedback.',
            who_we_are_looking_for='A thoughtful writer.',
            engagement_type='volunteer',
            work_mode='remote',
            location='Nigeria',
            time_commitment='4 to 6 hours per week',
            status='open',
            positions_available=5,
        )
        self.filled_vacancy = Vacancy.objects.create(
            title='Volunteer Designer',
            slug='volunteer-designer',
            summary='Design useful materials.',
            description='Help us communicate visually.',
            expectations='Reliable communication.',
            responsibilities='Design campaign assets.',
            benefits='Portfolio experience.',
            who_we_are_looking_for='A thoughtful designer.',
            status='filled',
        )

    def application_data(
        self,
        email='applicant@example.com',
        newsletter_opt_in=False,
    ):
        data = {
            'full_name': 'Example Applicant',
            'email': email,
            'phone': '+2348000000000',
            'cv': SimpleUploadedFile(
                'cv.pdf',
                b'example cv',
                content_type='application/pdf',
            ),
            'cover_letter': 'I would like to help.',
            'consent': 'on',
        }
        if newsletter_opt_in:
            data['newsletter_opt_in'] = 'on'
        return data

    def test_list_is_public_and_shows_open_and_filled_roles(self):
        response = self.client.get(reverse('opportunities:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vacancy.title)
        self.assertContains(response, self.filled_vacancy.title)
        self.assertContains(response, '<h2>Careers</h2>', html=True)
        self.assertNotContains(response, 'Work with OEF')
        self.assertContains(response, '5 positions')
        self.assertContains(response, self.vacancy.team)
        self.assertContains(response, self.vacancy.time_commitment)
        self.assertContains(
            response,
            'View More',
            count=len(response.context['vacancies']),
        )
        self.assertNotContains(response, 'View and apply')
        self.assertNotContains(response, 'View role')

    def test_writer_is_the_first_open_role_in_catalogue_order(self):
        Vacancy.objects.create(
            title='Another open role',
            slug='another-open-role',
            summary='Another role.',
            description='Another role.',
            expectations='Be reliable.',
            responsibilities='Help the team.',
            benefits='Gain experience.',
            who_we_are_looking_for='A collaborator.',
            status='open',
            display_order=50,
        )
        self.vacancy.display_order = 10
        self.vacancy.save(update_fields=('display_order',))

        response = self.client.get(reverse('opportunities:list'))
        roles = list(response.context['vacancies'])

        self.assertEqual(roles[0], self.vacancy)

    def test_vacancy_detail_is_public_and_does_not_require_sign_in(self):
        response = self.client.get(self.vacancy.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h2>Career Opportunity</h2>', html=True)
        self.assertContains(response, 'No account is required')
        self.assertNotContains(response, 'Sign in to apply')
        self.assertContains(response, 'About OEF')
        self.assertContains(response, 'Core responsibilities')
        self.assertContains(response, '<li>Write articles.</li>', html=True)
        self.assertContains(
            response,
            'Send me OEF news and programme updates.',
        )

    def test_guest_can_apply_without_an_account(self):
        response = self.client.post(
            reverse('opportunities:apply', kwargs={'slug': self.vacancy.slug}),
            self.application_data(),
        )

        self.assertRedirects(response, self.vacancy.get_absolute_url())
        application = VacancyApplication.objects.get()
        self.assertEqual(application.email, 'applicant@example.com')
        self.assertEqual(application.full_name, 'Example Applicant')
        self.assertIsNone(application.applicant)
        self.assertFalse(application.newsletter_opt_in)
        self.assertTrue(
            application.cv.name.startswith('vacancy_applications/private_cv/')
        )
        self.assertTrue(application.cv.name.endswith('.pdf'))
        self.mock_notify_new_application.assert_called_once_with(
            application,
            site_url='http://testserver/',
            admin_url='http://testserver' + reverse(
                'admin:opportunities_vacancyapplication_change',
                args=(application.pk,),
            ),
        )

    def test_guest_can_explicitly_opt_in_to_newsletter_updates(self):
        self.client.post(
            reverse('opportunities:apply', kwargs={'slug': self.vacancy.slug}),
            self.application_data(newsletter_opt_in=True),
        )

        self.assertTrue(VacancyApplication.objects.get().newsletter_opt_in)

    def test_duplicate_email_can_only_apply_once(self):
        apply_url = reverse(
            'opportunities:apply',
            kwargs={'slug': self.vacancy.slug},
        )
        self.client.post(apply_url, self.application_data())
        response = self.client.post(
            apply_url,
            self.application_data(email='APPLICANT@example.com'),
        )

        self.assertRedirects(response, self.vacancy.get_absolute_url())
        self.assertEqual(VacancyApplication.objects.count(), 1)

    def test_authenticated_application_is_linked_to_the_account(self):
        user = UserProfile.objects.create_user(
            email='member@example.com',
            password='test-password',
        )
        self.client.force_login(user)

        self.client.post(
            reverse('opportunities:apply', kwargs={'slug': self.vacancy.slug}),
            self.application_data(email=user.email),
        )

        self.assertEqual(VacancyApplication.objects.get().applicant, user)

    def test_filled_role_rejects_applications(self):
        response = self.client.post(
            reverse(
                'opportunities:apply',
                kwargs={'slug': self.filled_vacancy.slug},
            ),
            self.application_data(),
        )

        self.assertRedirects(response, self.filled_vacancy.get_absolute_url())
        self.assertEqual(VacancyApplication.objects.count(), 0)


class VacancyNotificationTests(TestCase):
    def setUp(self):
        self.vacancy = Vacancy.objects.create(
            title='Volunteer Content Writer',
            slug='notification-writer',
            summary='Write useful stories.',
            description='Help OEF communicate clearly.',
            expectations='Communicate reliably.',
            responsibilities='Write and edit.',
            benefits='Build practical experience.',
            who_we_are_looking_for='A thoughtful writer.',
            status='open',
        )
        self.application = VacancyApplication.objects.create(
            vacancy=self.vacancy,
            full_name='Ayo <Applicant>',
            email='ayo@example.com',
            phone='+2348000000000',
            cv='vacancy_applications/cv/ayo.pdf',
            cover_letter='I would like to help.',
        )

    @override_settings(
        BREVO_VACANCY_ACK_TEMPLATE_ID=42,
        SLACK_VACANCIES_WEBHOOK_URL='https://hooks.slack.test/vacancies',
        OEF_PUBLIC_SITE_URL='https://www.example.org',
        VACANCY_APPLICATION_RESPONSE_WINDOW='3 working days',
    )
    @patch('opportunities.notifications.upsert_newsletter_contact')
    @patch('opportunities.notifications.post_slack_webhook')
    @patch('opportunities.notifications.send_template_email')
    def test_sends_brevo_template_email_and_private_slack_review_notice(
        self,
        mock_send_template_email,
        mock_post_slack,
        mock_upsert_newsletter_contact,
    ):
        result = notify_new_application(
            self.application,
            site_url='https://www.example.org/',
            admin_url='https://www.example.org/admin/applications/1/',
        )

        self.assertTrue(result)
        self.application.refresh_from_db()
        self.assertIsNotNone(self.application.acknowledgement_sent_at)
        self.assertIsNotNone(self.application.slack_notified_at)
        self.assertIsNone(self.application.newsletter_subscribed_at)
        self.assertEqual(self.application.notification_error, '')
        mock_upsert_newsletter_contact.assert_not_called()

        email_kwargs = mock_send_template_email.call_args.kwargs
        self.assertEqual(email_kwargs['destination'], 'ayo@example.com')
        self.assertEqual(email_kwargs['template_id'], 42)
        self.assertEqual(email_kwargs['params']['first_name'], 'Ayo')
        self.assertEqual(
            email_kwargs['params']['role_title'],
            'Volunteer Content Writer',
        )
        self.assertEqual(
            email_kwargs['params']['response_window'],
            '3 working days',
        )
        self.assertEqual(
            email_kwargs['params']['home_url'],
            'https://www.example.org/',
        )
        self.assertNotIn('newsletter_url', email_kwargs['params'])
        self.assertEqual(
            email_kwargs['params']['news_url'],
            'https://www.example.org/article/all/',
        )
        self.assertNotIn('facebook_url', email_kwargs['params'])

        slack_kwargs = mock_post_slack.call_args.kwargs
        self.assertEqual(
            slack_kwargs['webhook_url'],
            'https://hooks.slack.test/vacancies',
        )
        payload = mock_post_slack.call_args.args[0]
        self.assertEqual(payload['blocks'][0]['text']['text'], 'New OEF vacancy application')
        self.assertIn('I would like to help.', payload['blocks'][2]['text']['text'])
        self.assertEqual(
            payload['blocks'][3]['elements'][0]['text']['text'],
            'Download CV',
        )
        self.assertIn(
            '/media/vacancy_applications/cv/ayo.pdf',
            payload['blocks'][3]['elements'][0]['url'],
        )
        self.assertEqual(
            payload['blocks'][3]['elements'][1]['url'],
            'https://www.example.org/admin/applications/1/',
        )
        self.assertIn('Ayo &lt;Applicant&gt;', str(payload))

        self.assertTrue(
            notify_new_application(
                self.application,
                site_url='https://www.example.org/',
                admin_url='https://www.example.org/admin/applications/1/',
            )
        )
        mock_send_template_email.assert_called_once()
        mock_post_slack.assert_called_once()

    @override_settings(
        BREVO_VACANCY_ACK_TEMPLATE_ID=42,
        SLACK_VACANCIES_WEBHOOK_URL='https://hooks.slack.test/vacancies',
    )
    @patch('opportunities.notifications.upsert_newsletter_contact')
    @patch('opportunities.notifications.post_slack_webhook')
    @patch('opportunities.notifications.send_template_email')
    def test_subscribes_only_when_the_applicant_explicitly_opts_in(
        self,
        mock_send_template_email,
        mock_post_slack,
        mock_upsert_newsletter_contact,
    ):
        self.application.newsletter_opt_in = True
        self.application.save(update_fields=('newsletter_opt_in',))

        self.assertTrue(
            notify_new_application(
                self.application,
                site_url='https://www.example.org/',
                admin_url='https://www.example.org/admin/applications/1/',
            )
        )

        self.application.refresh_from_db()
        self.assertIsNotNone(self.application.newsletter_subscribed_at)
        mock_upsert_newsletter_contact.assert_called_once_with(
            'ayo@example.com',
            attributes={'SOURCE': 'Vacancy application'},
        )
        mock_send_template_email.assert_called_once()
        mock_post_slack.assert_called_once()

    @override_settings(
        BREVO_VACANCY_ACK_TEMPLATE_ID=42,
        SLACK_VACANCIES_WEBHOOK_URL='https://hooks.slack.test/vacancies',
    )
    @patch(
        'opportunities.notifications.post_slack_webhook',
        side_effect=RuntimeError('slack unavailable'),
    )
    @patch(
        'opportunities.notifications.send_template_email',
        side_effect=RuntimeError('email unavailable'),
    )
    @patch(
        'opportunities.notifications.upsert_newsletter_contact',
        side_effect=RuntimeError('newsletter unavailable'),
    )
    def test_records_provider_failures_without_deleting_application(
        self,
        mock_upsert_newsletter_contact,
        mock_send_template_email,
        mock_post_slack,
    ):
        self.application.newsletter_opt_in = True
        self.application.save(update_fields=('newsletter_opt_in',))
        result = notify_new_application(
            self.application,
            site_url='https://www.example.org/',
            admin_url='https://www.example.org/admin/applications/1/',
        )

        self.assertFalse(result)
        self.application.refresh_from_db()
        self.assertTrue(
            VacancyApplication.objects.filter(pk=self.application.pk).exists()
        )
        self.assertIsNone(self.application.acknowledgement_sent_at)
        self.assertIsNone(self.application.slack_notified_at)
        self.assertIsNone(self.application.newsletter_subscribed_at)
        self.assertIn(
            'Newsletter: newsletter unavailable',
            self.application.notification_error,
        )
        self.assertIn('Applicant email: email unavailable', self.application.notification_error)
        self.assertIn('Slack: slack unavailable', self.application.notification_error)
        mock_upsert_newsletter_contact.assert_called_once()
        mock_send_template_email.assert_called_once()
        mock_post_slack.assert_called_once()


class VacancyCVStorageTests(TestCase):
    @override_settings(
        CLOUDINARY_STORAGE={
            'CLOUD_NAME': 'test-cloud',
            'API_KEY': 'test-key',
            'API_SECRET': 'test-secret',
        },
        VACANCY_CV_LINK_TTL_SECONDS=604800,
    )
    @patch(
        'opportunities.storage.cloudinary.utils.private_download_url',
        return_value='https://cloudinary.test/signed-cv',
    )
    @patch('opportunities.storage.cloudinary.uploader.upload')
    @patch('opportunities.storage.time.time', return_value=1000)
    def test_uses_authenticated_raw_upload_and_expiring_signed_url(
        self,
        mock_time,
        mock_upload,
        mock_private_download_url,
    ):
        storage = VacancyCVStorage()._backend(
            'vacancy_applications/private_cv/application.pdf'
        )
        self.assertIsInstance(storage, AuthenticatedRawCloudinaryStorage)

        content = ContentFile(b'example cv', name='application.pdf')
        storage._upload(
            'vacancy_applications/private_cv/application.pdf',
            content,
        )
        mock_upload.assert_called_once_with(
            content,
            public_id='vacancy_applications/private_cv/application.pdf',
            resource_type='raw',
            type='authenticated',
            overwrite=False,
            tags=storage.TAG,
        )

        self.assertEqual(
            storage.url('vacancy_applications/private_cv/application.pdf'),
            'https://cloudinary.test/signed-cv',
        )
        mock_private_download_url.assert_called_once_with(
            'media/vacancy_applications/private_cv/application',
            'pdf',
            resource_type='raw',
            type='authenticated',
            attachment=True,
            expires_at=605800,
        )
        mock_time.assert_called_once()

    @override_settings(
        CLOUDINARY_STORAGE={
            'CLOUD_NAME': 'test-cloud',
            'API_KEY': 'test-key',
            'API_SECRET': 'test-secret',
        },
        VACANCY_CV_LINK_TTL_SECONDS=604800,
    )
    @patch(
        'opportunities.storage.cloudinary.utils.private_download_url',
        return_value='https://cloudinary.test/signed-existing-cv',
    )
    @patch('opportunities.storage.time.time', return_value=1000)
    def test_media_prefixed_private_cv_still_uses_cloudinary_signed_url(
        self,
        mock_time,
        mock_private_download_url,
    ):
        storage = VacancyCVStorage()

        self.assertEqual(
            storage.url('media/vacancy_applications/private_cv/application.pdf'),
            'https://cloudinary.test/signed-existing-cv',
        )
        mock_private_download_url.assert_called_once_with(
            'media/vacancy_applications/private_cv/application',
            'pdf',
            resource_type='raw',
            type='authenticated',
            attachment=True,
            expires_at=605800,
        )
        mock_time.assert_called_once()

    @override_settings(
        CLOUDINARY_STORAGE={
            'CLOUD_NAME': 'test-cloud',
            'API_KEY': 'test-key',
            'API_SECRET': 'test-secret',
        },
    )
    @patch(
        'opportunities.storage.AuthenticatedRawCloudinaryStorage.save',
        return_value='media/vacancy_applications/private_cv/application.pdf',
    )
    def test_save_stores_canonical_private_cv_name(self, mock_save):
        storage = VacancyCVStorage()
        content = ContentFile(b'example cv', name='application.pdf')

        self.assertEqual(
            storage._save(
                'vacancy_applications/private_cv/application.pdf',
                content,
            ),
            'vacancy_applications/private_cv/application.pdf',
        )
        mock_save.assert_called_once_with(
            'vacancy_applications/private_cv/application.pdf',
            content,
        )


class SeedVacanciesTests(TestCase):
    def setUp(self):
        Vacancy.objects.all().delete()
        self.source_directory = tempfile.TemporaryDirectory()
        self.source = Path(self.source_directory.name, 'vacancies.md')
        self.source.write_text(catalogue_markdown(), encoding='utf-8')

    def tearDown(self):
        self.source_directory.cleanup()

    def import_catalogue(self, **options):
        call_command(
            'seed_vacancies',
            source=str(self.source),
            verbosity=0,
            **options,
        )

    def test_command_creates_the_complete_catalogue_without_duplicates(self):
        self.import_catalogue()
        self.import_catalogue()

        self.assertEqual(Vacancy.objects.count(), 2)
        writer = Vacancy.objects.get(slug='test-writer')
        self.assertEqual(writer.status, 'open')
        self.assertEqual(writer.positions_available, 5)
        self.assertEqual(writer.catalogue_version, 3)
        self.assertEqual(writer.about_oef, 'OEF supports underserved communities.')
        self.assertTrue(writer.team)
        self.assertTrue(writer.time_commitment)
        self.assertEqual(
            Vacancy.objects.get(slug='test-designer').status,
            'filled',
        )

    def test_command_updates_an_outdated_catalogue_record(self):
        Vacancy.objects.update_or_create(
            slug='test-writer',
            defaults={
                'title': 'Old writer title',
                'summary': 'Old summary',
                'description': 'Old description',
                'expectations': 'Old expectations',
                'responsibilities': 'Old responsibilities',
                'benefits': 'Old benefits',
                'who_we_are_looking_for': 'Old profile',
                'catalogue_version': 0,
                'status': 'draft',
            },
        )

        self.import_catalogue()

        writer = Vacancy.objects.get(slug='test-writer')
        self.assertEqual(writer.title, 'Test Writer')
        self.assertEqual(writer.status, 'open')
        self.assertEqual(writer.catalogue_version, 3)

    def test_command_preserves_admin_edits_at_the_current_catalogue_version(self):
        self.import_catalogue()
        writer = Vacancy.objects.get(slug='test-writer')
        writer.summary = 'Admin-edited summary'
        writer.save(update_fields=('summary',))

        self.import_catalogue()

        writer.refresh_from_db()
        self.assertEqual(writer.summary, 'Admin-edited summary')

    def test_force_reapplies_current_catalogue_content(self):
        self.import_catalogue()
        writer = Vacancy.objects.get(slug='test-writer')
        writer.summary = 'Admin-edited summary'
        writer.save(update_fields=('summary',))

        self.import_catalogue(force=True)

        writer.refresh_from_db()
        self.assertEqual(writer.summary, 'Write useful stories.')

    def test_dry_run_validates_without_writing(self):
        self.import_catalogue(dry_run=True)

        self.assertEqual(Vacancy.objects.count(), 0)

    def test_command_rejects_a_catalogue_missing_required_fields(self):
        self.source.write_text(
            dedent(
                '''
                # Invalid catalogue

                ```yaml
                catalogue_version: 1
                vacancies:
                  - slug: incomplete-role
                    title: Incomplete Role
                ```
                '''
            ).strip(),
            encoding='utf-8',
        )

        with self.assertRaisesMessage(CommandError, 'missing required fields'):
            self.import_catalogue()
