import random
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from user.forms import (CustomPasswordResetForm, UsernameForm,
                        UserRegistrationForm, UserUpdateForm,
                        VolunteerRegistrationForm, VolunteerUpdateForm)
from user.management.services import SiteService
from utils.enums import EthnicityEnum, ReligionEnum, StateEnum


class MockObjects:

    def render_to_string(self):
        return 'This is an email'


class FormsTestCase(TestCase):
    mock = MockObjects()

    def setUp(self):
        self.host = 'google.com'
        self.name = 'Example Site'
        self.site = SiteService.add_site(domain=self.host, name=self.name)
        self.factory = RequestFactory()

    def test_user_registration_form(self):
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'username': 'johndoe',
            'email': 'johndoe@example.com',
            'password1': 'testpassword',
            'password2': 'testpassword',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_user_update_form(self):
        user_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'johndoe@example.com',
        }
        form = UserUpdateForm(data=user_data)
        self.assertTrue(form.is_valid())

    def test_volunteer_registration_form(self):
        form_data = {
            'phone_number': '1234567890',
            'state_of_residence': random.choice(list(StateEnum)).value,
        }
        form = VolunteerRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_volunteer_update_form(self):
        image_data = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
            b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
            b'\x02\x4c\x01\x00\x3b'
        )
        image_file = SimpleUploadedFile("test_image.jpg", image_data, content_type='image/jpeg')

        form_data = {
            'phone_number': '1234567890',
            'profession': 'Teacher',
            'ethnicity': random.choice(list(EthnicityEnum)).value,
            'religion': random.choice(list(ReligionEnum)).value,
            'state_of_residence': random.choice(list(StateEnum)).value,
            'short_bio': 'I am a volunteer.',
        }
        form = VolunteerUpdateForm(form_data, {'image': image_file})
        form.is_valid()
        self.assertTrue(form.is_valid())

    @patch('django.contrib.sites.shortcuts.get_current_site')
    @patch('django.template.loader.render_to_string')
    @patch('ext_libs.sendgrid.sengrid.send_email')
    def test_custom_password_reset_form(self, mock_send_email, mock_render_to_string, mock_get_current_site):
        form_data = {
            'email': 'testuser@example.com',
        }
        mock_get_current_site.get_current_site.return_value = self.host
        form = CustomPasswordResetForm(data=form_data)
        self.assertTrue(form.is_valid())
        form.save()

        context = {'site_name': 'Example Site'}
        to_email = 'testuser@example.com'

        mock_render_to_string.return_value = self.mock.render_to_string()
        mock_send_email.return_value = True
        form.send_mail(context, to_email)

        mock_get_current_site.assert_called_once()
        mock_render_to_string.assert_called_once_with(
            'registration/password_reset_email.html', context
        )
        mock_send_email.assert_called_once_with(
            destination=to_email,
            subject=f"Password reset on {self.name}",
            content=mock_render_to_string.return_value
        )

    def test_username_form(self):
        form_data = {
            'username': 'johndoe',
        }
        form = UsernameForm(data=form_data)
        self.assertTrue(form.is_valid())
