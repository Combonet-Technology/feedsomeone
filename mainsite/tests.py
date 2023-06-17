from django.test import TestCase
from django.urls import resolve

from .views import home


class SmokeTest(TestCase):

    def test_random(self):
        self.assertEqual(1 + 1, 2)


class HomePage(TestCase):
    def test_root_url_resolves_to_homepage(self):
        home_path = resolve('/')
        self.assertEqual(home_path.func, home)
