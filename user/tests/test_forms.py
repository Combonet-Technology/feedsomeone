import random

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

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
        User = get_user_model()
        user = User.objects.create_user(username='testuser', email='testuser@example.com')
        form_data = {
            'email': 'testuser@example.com',
        }
        form = CustomPasswordResetForm(data=form_data)
        assert form.cleaned_data["email"] == form_data['email']
        form.save()
        self.assertTrue(form.is_valid())

        # Generate a password reset token for the user
        token = default_token_generator.make_token(user)

        # Build the password reset URL
        reset_url = reverse('password_reset_confirm', args=[urlsafe_base64_encode(force_bytes(user.pk)), token])

        # Make a GET request to the password reset URL
        response = self.client.get(reset_url)

        # Check that the response status code is 200 (OK)
        self.assertEqual(response.status_code, 200)

        # Check that the password reset form is rendered
        self.assertTemplateUsed(response, 'password_reset_confirm.html')

        # Extract the context from the response
        context = response.context

        # Check the values in the context
        self.assertEqual(context['email'], user.email)
        self.assertEqual(context['uid'], urlsafe_base64_encode(force_bytes(user.pk)))
        self.assertEqual(context['token'], token)

    def test_username_form(self):
        form_data = {
            'username': 'johndoe',
        }
        form = UsernameForm(data=form_data)
        self.assertTrue(form.is_valid())
