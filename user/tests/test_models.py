import traceback
import unittest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from user.models import Donor, Lead, Volunteer
from utils.enums import EthnicityEnum, ReligionEnum, StateEnum


class CustomUserManagerTests(TestCase):

    def setUp(self):
        self.model = get_user_model()
        self.user_manager = self.model.objects
        self.user_data = {
            'email': 'test@mail.com',
            'password': 'password123'
        }
        self.superuser_data = {
            'email': 'admin@mail.com',
            'password': 'admin123'
        }

    def test_create_user(self):
        user = self.user_manager.create_user(**self.user_data)
        self.assertEqual(user.email, self.user_data['email'])
        self.assertTrue(user.check_password(self.user_data['password']))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        user = self.user_manager.create_superuser(**self.superuser_data)
        self.assertEqual(user.email, self.superuser_data['email'])
        self.assertTrue(user.check_password(self.superuser_data['password']))
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_create_user_existing_email(self):
        self.user_manager.create_user(**self.user_data)
        with transaction.atomic():
            self.assertRaises(IntegrityError, self.user_manager.create_user, **self.user_data)

    def test_create_user_invalid_data(self):
        with transaction.atomic():
            self.assertRaises(ValueError, self.user_manager.create_user, email='', password='password123')

    def test_create_superuser_existing_email(self):
        self.user_manager.create_superuser(**self.superuser_data)
        with transaction.atomic():
            self.assertRaises(IntegrityError, self.user_manager.create_superuser, **self.superuser_data)

    def test_create_superuser_invalid_data(self):
        with transaction.atomic():
            self.assertRaises(ValueError, self.user_manager.create_superuser, email='', password='admin123')

    def tearDown(self):
        try:
            self.user_manager.all().delete()
        except Exception as e:
            print("Exception occurred during tearDown: ", str(e))
            traceback.print_exc()


class UserProfileModelTests(TestCase):
    def setUp(self):
        self.model = get_user_model()
        self.user_manager = self.model.objects
        self.user_data = {
            'email': 'test@example.com',
            'password': 'password123',
            'first_name': 'John',
            'last_name': 'Doe',
        }

    def test_create_user_profile(self):
        profile = self.user_manager.create_user(**self.user_data)

        self.assertEqual(profile.email, self.user_data['email'])
        self.assertEqual(profile.first_name, self.user_data['first_name'])
        self.assertEqual(profile.last_name, self.user_data['last_name'])
        self.assertTrue(profile.is_active)
        self.assertFalse(profile.is_staff)
        self.assertFalse(profile.is_superuser)

    def test_create_user_profile_existing_email(self):
        self.user_manager.create_user(**self.user_data)
        with transaction.atomic():
            self.assertRaises(IntegrityError,
                              self.user_manager.create_user,
                              email=self.user_data['email'],
                              password='anotherpassword')

    def test_create_user_profile_invalid_data(self):
        with transaction.atomic():
            self.assertRaises(ValueError, self.user_manager.create_user, email='', password='password123')

    def tearDown(self):
        self.user_manager.all().delete()


class VolunteerModelTests(TestCase):
    def setUp(self):
        self.model = Volunteer
        self.user_model = get_user_model()
        self.user_manager = self.user_model.objects
        self.user_data = {
            'email': 'test@example.com',
            'password': 'password123',
            'first_name': 'John',
            'last_name': 'Doe',
        }
        self.volunteer_data = {
            'state_of_residence': StateEnum.ANAMBRA.value,
            'ethnicity': EthnicityEnum.YORUBA.value,
            'religion': ReligionEnum.CHRISTIANITY.value,
            'profession': 'Software Engineer',
            'short_bio': 'Passionate about giving back.',
            'phone_number': '1234567890',
        }

    def test_create_volunteer(self):
        user = self.user_manager.create_user(**self.user_data)
        volunteer = self.model.objects.create(user=user, **self.volunteer_data)

        self.assertEqual(volunteer.user, user)
        self.assertEqual(volunteer.state_of_residence, self.volunteer_data['state_of_residence'])
        self.assertEqual(volunteer.ethnicity, self.volunteer_data['ethnicity'])
        self.assertEqual(volunteer.religion, self.volunteer_data['religion'])
        self.assertEqual(volunteer.profession, self.volunteer_data['profession'])
        self.assertEqual(volunteer.short_bio, self.volunteer_data['short_bio'])
        self.assertEqual(volunteer.phone_number, self.volunteer_data['phone_number'])

    def tearDown(self):
        self.user_manager.all().delete()


class DonorModelTests(TestCase):
    def setUp(self):
        self.model = Donor
        self.user_model = get_user_model()
        self.user_manager = self.user_model.objects
        self.user_data = {
            'email': 'test@example.com',
            'password': 'password123',
            'first_name': 'John',
            'last_name': 'Doe',
        }

    def test_create_donor(self):
        user = self.user_manager.create_user(**self.user_data)
        donor = self.model.objects.create(user=user)

        self.assertEqual(donor.user, user)

    def tearDown(self):
        self.user_manager.all().delete()


class LeadModelTests(TestCase):
    def setUp(self):
        self.model = Lead
        self.lead_data = {
            'email': 'lead@example.com',
            'source': 'Website',
            'stage': 'New',
            'converted': False,
        }

    def test_create_lead(self):
        lead = self.model.objects.create(**self.lead_data)

        self.assertEqual(lead.email, self.lead_data['email'])
        self.assertEqual(lead.source, self.lead_data['source'])
        self.assertEqual(lead.stage, self.lead_data['stage'])
        self.assertEqual(lead.converted, self.lead_data['converted'])

    def test_create_lead_duplicate_email(self):
        self.model.objects.create(**self.lead_data)
        with transaction.atomic():
            self.assertRaises(IntegrityError, self.model.objects.create, **self.lead_data)

    def test_create_lead_invalid_email(self):
        lead_data = self.lead_data.copy()
        lead_data['email'] = 'invalid_email'
        with transaction.atomic():
            self.assertRaises(ValidationError, self.model.objects.create, **lead_data)

    def tearDown(self):
        self.model.objects.all().delete()


if __name__ == '__main__':
    unittest.main()
