from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from user.models import UserProfile

from .models import Vacancy, VacancyApplication


class VacancyApplicationTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(email='applicant@example.com', password='test-password')
        self.vacancy = Vacancy.objects.create(
            title='Volunteer Writer', slug='volunteer-writer', summary='Write useful stories.',
            description='Help us tell impact stories.', expectations='Reliable communication.',
            responsibilities='Write and edit articles.', benefits='Portfolio experience.',
            who_we_are_looking_for='A thoughtful writer.',
        )

    def test_vacancy_is_public(self):
        response = self.client.get(reverse('opportunities:detail', kwargs={'slug': self.vacancy.slug}))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_can_apply_once(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('opportunities:apply', kwargs={'slug': self.vacancy.slug}),
            {
                'cv': SimpleUploadedFile('cv.pdf', b'cv', content_type='application/pdf'),
                'cover_letter': 'I would like to help.',
            },
        )
        self.assertRedirects(response, self.vacancy.get_absolute_url())
        self.assertEqual(VacancyApplication.objects.count(), 1)
        response = self.client.post(
            reverse('opportunities:apply', kwargs={'slug': self.vacancy.slug}),
            {'cv': SimpleUploadedFile('cv.pdf', b'cv', content_type='application/pdf'), 'cover_letter': 'Again.'},
        )
        self.assertRedirects(response, self.vacancy.get_absolute_url())
        self.assertEqual(VacancyApplication.objects.count(), 1)
