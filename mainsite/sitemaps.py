from urllib.parse import urlsplit, urlunsplit

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class CanonicalDomainSitemap(Sitemap):
    protocol = 'https'
    canonical_domain = 'www.oluwafemiebenezerfoundation.org'

    def get_urls(self, page=1, site=None, protocol=None):
        urls = super().get_urls(
            page=page,
            site=site,
            protocol=protocol or self.protocol,
        )
        for url_info in urls:
            parts = urlsplit(url_info['location'])
            url_info['location'] = urlunsplit((
                self.protocol,
                self.canonical_domain,
                parts.path,
                parts.query,
                parts.fragment,
            ))
        return urls


class StaticViewSitemap(CanonicalDomainSitemap):
    changefreq = 'monthly'
    priority = 0.8

    def items(self):
        return [
            'mainsite:homepage',
            'mainsite:about-page',
            'mainsite:what-is-oef',
            'mainsite:impact',
            'mainsite:transparency',
            'mainsite:gallery',
            'events',
            'contact',
            'article:all-articles',
            'volunteer-list',
        ]

    def location(self, item):
        return reverse(item)
