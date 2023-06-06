import unittest

from django.contrib.auth import get_user_model
from django.db import IntegrityError


class CustomUserManagerTests(unittest.TestCase):

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
        with self.assertRaises(IntegrityError):
            self.user_manager.create_user(**self.user_data)

    def test_create_user_invalid_data(self):
        with self.assertRaises(ValueError):
            self.user_manager.create_user(email='', password='password123')

    def test_create_superuser_existing_email(self):
        self.user_manager.create_superuser(**self.superuser_data)
        with self.assertRaises(IntegrityError):
            self.user_manager.create_superuser(**self.superuser_data)

    def test_create_superuser_invalid_data(self):
        with self.assertRaises(ValueError):
            self.user_manager.create_superuser(email='', password='admin123')

    def tearDown(self):
        self.user_manager.all().delete()


if __name__ == '__main__':
    unittest.main()
