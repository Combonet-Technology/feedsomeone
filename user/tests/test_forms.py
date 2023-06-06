import random

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from user.enums import EthnicityEnum, ReligionEnum, StateEnum
from user.forms import (CustomPasswordResetForm, UsernameForm,
                        UserRegistrationForm, UserUpdateForm,
                        VolunteerRegistrationForm, VolunteerUpdateForm)


class FormsTestCase(TestCase):
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

    def test_custom_password_reset_form(self):
        form_data = {
            'email': 'johndoe@example.com',
        }
        form = CustomPasswordResetForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_username_form(self):
        form_data = {
            'username': 'johndoe',
        }
        form = UsernameForm(data=form_data)
        self.assertTrue(form.is_valid())
