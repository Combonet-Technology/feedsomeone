from mainsite.sitemaps import CanonicalDomainSitemap

from .models import Vacancy


class VacancySitemap(CanonicalDomainSitemap):
    """Advertised vacancy pages, computed from current public records."""

    def items(self):
        return Vacancy.objects.filter(is_active=True).exclude(status='draft')

    def lastmod(self, vacancy):
        return vacancy.updated_at
