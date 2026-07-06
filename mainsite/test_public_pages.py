from html.parser import HTMLParser
from urllib.parse import urlsplit

from django.test import TestCase
from django.urls import Resolver404, resolve, reverse


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        href = dict(attrs).get('href')
        if href:
            self.hrefs.append(href)


class PublicPageTests(TestCase):
    public_routes = (
        'mainsite:homepage',
        'mainsite:about-page',
        'mainsite:impact',
        'mainsite:transparency',
        'mainsite:gallery',
        'mainsite:privacy',
    )

    def test_primary_public_pages_render(self):
        for route in self.public_routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)

    def test_primary_public_pages_have_no_unresolvable_internal_links(self):
        broken_links = []
        for route in self.public_routes:
            response = self.client.get(reverse(route))
            parser = LinkCollector()
            parser.feed(response.content.decode())
            for href in parser.hrefs:
                parsed = urlsplit(href)
                if parsed.scheme or parsed.netloc or not parsed.path or parsed.path == '#':
                    continue
                try:
                    resolve(parsed.path)
                except Resolver404:
                    broken_links.append((route, href))

        self.assertEqual(broken_links, [])

    def test_public_identity_and_programme_relationship_are_explicit(self):
        home = self.client.get(reverse('mainsite:homepage'))
        about = self.client.get(reverse('mainsite:about-page'))

        self.assertContains(home, 'Oluwafemi Ebenezer Foundation')
        self.assertContains(about, 'flagship relief programme')
        self.assertContains(about, 'Founded from the Feed Someone outreach conceived in 2019')
