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
        'mainsite:what-is-oef',
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
        explainer = self.client.get(reverse('mainsite:what-is-oef'))

        self.assertContains(home, 'Oluwafemi Ebenezer Foundation')
        self.assertContains(about, 'flagship relief programme')
        self.assertContains(about, 'Founded from the Feed Someone outreach conceived in 2019')
        self.assertContains(explainer, 'OEF is not a children-only or orphanage-only charity')
        self.assertContains(explainer, 'Feed Someone is the founding movement and flagship outreach initiative')

    def test_sitemap_uses_canonical_www_domain_and_grant_review_routes(self):
        response = self.client.get('/sitemap.xml')
        content = response.content.decode()
        canonical_base = 'https://www.oluwafemiebenezerfoundation.org'

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('https://oluwafemiebenezerfoundation.org/', content)
        for path in (
            '/',
            '/about/',
            '/what-is-oluwafemi-ebenezer-foundation/',
            '/impact/',
            '/transparency/',
            '/gallery/',
            '/events/',
            '/contact/',
            '/article/all/',
            '/volunteers/view-volunteers/',
        ):
            self.assertIn(
                canonical_base + path,
                content,
            )

    def test_key_public_pages_have_unique_meta_descriptions(self):
        routes = (
            'mainsite:homepage',
            'mainsite:about-page',
            'mainsite:what-is-oef',
            'mainsite:impact',
            'mainsite:transparency',
            'mainsite:gallery',
        )
        descriptions = {}

        for route in routes:
            response = self.client.get(reverse(route))
            content = response.content.decode()
            marker = '<meta name="description" content="'
            start = content.find(marker)
            self.assertNotEqual(start, -1, route)
            start += len(marker)
            end = content.find('"', start)
            description = content[start:end]
            self.assertGreater(len(description), 80, route)
            descriptions[route] = description

        self.assertEqual(len(set(descriptions.values())), len(descriptions))

    def test_transparency_page_exposes_faq_schema(self):
        response = self.client.get(reverse('mainsite:transparency'))
        content = response.content.decode()

        self.assertContains(response, '"@type": "FAQPage"')
        self.assertContains(response, 'Is Oluwafemi Ebenezer Foundation registered?')
        self.assertContains(response, 'CAC registration number: 179189')
        self.assertIn('info@oluwafemiebenezerfoundation.org', content)
