import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from user.models import UserProfile

from .models import Vacancy, VacancyApplication


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
        self.vacancy = Vacancy.objects.create(
            title='Volunteer Writer',
            slug='volunteer-writer',
            summary='Write useful stories.',
            description='Help us tell impact stories.',
            expectations='Reliable communication.',
            responsibilities='Write and edit articles.',
            benefits='Portfolio experience.',
            who_we_are_looking_for='A thoughtful writer.',
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

    def application_data(self, email='applicant@example.com'):
        return {
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

    def test_list_is_public_and_shows_open_and_filled_roles(self):
        response = self.client.get(reverse('opportunities:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vacancy.title)
        self.assertContains(response, self.filled_vacancy.title)
        self.assertContains(response, '5 positions')

    def test_vacancy_detail_is_public_and_does_not_require_sign_in(self):
        response = self.client.get(self.vacancy.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No account is required')
        self.assertNotContains(response, 'Sign in to apply')

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


class SeedVacanciesTests(TestCase):
    def test_command_creates_and_updates_expected_roles(self):
        call_command('seed_vacancies', verbosity=0)
        call_command('seed_vacancies', verbosity=0)

        self.assertEqual(Vacancy.objects.count(), 3)
        writer = Vacancy.objects.get(slug='volunteer-content-writer')
        self.assertEqual(writer.status, 'open')
        self.assertEqual(writer.positions_available, 5)
        self.assertEqual(
            Vacancy.objects.get(slug='volunteer-graphic-designer').status,
            'filled',
        )
        self.assertEqual(
            Vacancy.objects.get(slug='volunteer-project-manager').status,
            'filled',
        )
