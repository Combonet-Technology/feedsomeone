import random
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.forms import ImageField
from django.test import RequestFactory, TestCase
from django.test.client import Client
from django.urls import reverse

from user.enums import EthnicityEnum, ReligionEnum, StateEnum
from user.management.services import SiteService
from user.models import Volunteer

User = get_user_model()


class ProfileViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.host = 'example.com'
        self.site = SiteService.add_site(domain=self.host, name='Example Site')
        self.client = Client()
        self.user = User.objects.create_user(email='test@mail.com', password='testpassword')
        self.client.login(email='test@mail.com', password='testpassword')
        self.volunteer = Volunteer.objects.create(phone_number='123456789', state_of_residence=StateEnum.ANAMBRA.value)
        self.volunteer.user = self.user
        self.volunteer.save()
        self.url = reverse('profile')

    def test_profile_get_request(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profile.html')
        self.assertEqual(response.context['user'], self.volunteer)

    def test_post_request_valid_form(self):
        image_file = mock.MagicMock(spec=ImageField)
        image_file.name = 'test_image.jpg'
        image_file.content_type = 'image/jpeg'

        form_data = {
            'phone_number': '1234567890',
            'profession': 'Teacher',
            'ethnicity': random.choice(list(EthnicityEnum)).value,
            'religion': random.choice(list(ReligionEnum)).value,
            'state_of_residence': random.choice(list(StateEnum)).value,
            'short_bio': 'I am a volunteer.',
        }
        response = self.client.post(self.url, data=form_data, files=image_file, follow=True)
        self.assertEqual(len(response.context['messages']), 1)
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(list(messages)[0]), f'Account for {self.volunteer.user} updated Successfully!')
        self.assertEqual(response.status_code, 200)

    def test_post_request_invalid_form(self):
        form_data = {
        }
        response = self.client.post(self.url, data=form_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user_update_form'].is_bound)
        self.assertFalse(response.context['user_update_form'].is_valid())

    def test_get_request_other_user(self):
        self.client.logout()
        response = self.client.get(self.url, HTTP_HOST='example.com')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/login/?next=/volunteers/profile/')

    def test_post_request_unauthenticated(self):
        self.client.logout()
        form_data = {}
        response = self.client.post(self.url, HTTP_HOST='example.com', data=form_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/login/?next=/volunteers/profile/')
