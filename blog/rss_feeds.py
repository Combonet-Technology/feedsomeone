from django.contrib.syndication.views import Feed
from django.template.defaultfilters import truncatewords
from django.urls import reverse_lazy

from .models import Article


class LatestArticlesFeed(Feed):
    title = 'OLUWAFEMI EBENEZER FOUNDATION BLOG'
    link = reverse_lazy('article:all-articles')
    description = 'Get all our published articles about events and hacks from our brilliant volunteer writers.'

    def items(self):
        return Article.published.all()[:5]

    def item_title(self, item):
        return item.article_title

    def item_description(self, item):
        return truncatewords(item.article_content, 30)
