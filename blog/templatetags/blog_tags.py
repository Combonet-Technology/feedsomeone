from django import template

from ..models import Article, Categories

register = template.Library()


@register.simple_tag(name='total_articles_count')
def total_posts():
    return Article.published.count()


@register.simple_tag(name='total_articles_year')
def total_annual_posts():
    return Article.published.count()


@register.simple_tag(name='total_articles_month')
def total_monthly_posts():
    return Article.published.count()


@register.simple_tag(name='total_articles_week')
def total_weekly_posts():
    return Article.published.count()


@register.simple_tag(name='total_articles_today')
def total_daily_posts():
    return Article.published.count()


@register.inclusion_tag('blog/latest.html')
def show_recent_articles(count=5):
    recent_articles = Article.published.order_by('-publish_date')[:count]
    return {'recent_articles': recent_articles}


@register.inclusion_tag('blog/latest.html')
def show_all_categories(count=5):
    categories = Categories.objects.all()[:count]
    return {'categories': categories}
