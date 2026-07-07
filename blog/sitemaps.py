from mainsite.sitemaps import CanonicalDomainSitemap

from .models import Article


class ArticleSitemap(CanonicalDomainSitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return Article.published.all()

    def lastmod(self, obj):
        return obj.date_updated
