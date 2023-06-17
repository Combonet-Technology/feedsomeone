from django.http import HttpRequest
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

    def test_homepage_returns_valid_data(self):
        request = HttpRequest()
        response = home(request)
        html_content = response.content.decode('utf-8').strip()
        self.assertTrue(html_content.startswith('<!doctype html>'))
        self.assertTrue(html_content.endswith('</html>'))
        self.assertIn('<title>FEEDSOMEONE | eradicating hunger and poverty</title>', html_content)
