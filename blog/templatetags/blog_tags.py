from typing import Optional

import markdown
from django import template
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.safestring import mark_safe
from taggit.models import Tag

from ..models import Article, Categories

register = template.Library()


@register.simple_tag(name='total_articles_count')
def total_posts() -> int:
    return Article.published.count()


@register.simple_tag(name='total_articles_year')
def total_annual_posts(year: Optional[int] = None) -> int:
    if not year:
        return Article.published.filter(publish_date__year=timezone.now().year).count()
    elif year <= timezone.now().year:
        return Article.published.filter(publish_date__year=year).count()
    else:
        return 0


@register.simple_tag(name='total_articles_month')
def total_monthly_posts(month: Optional[int] = None) -> int:
    if not month:
        return Article.published.filter(publish_date__year=timezone.now().year,
                                        publish_date__month=timezone.now().month).count()
    elif month <= 12 and month <= timezone.now().month and month >= 1:
        return Article.published.filter(publish_date__year=timezone.now().year, publish_date__month=month).count()
    else:
        return 0


@register.simple_tag(name='total_articles_week')
def total_weekly_posts(week: Optional[int] = None) -> int:
    if not week:
        return Article.published.filter(publish_date__year=timezone.now().year,
                                        publish_date__week=timezone.now().isocalendar()[1]).count()
    elif week <= 53 and week <= timezone.now().isocalendar()[1] and week >= 1:
        return Article.published.filter(publish_date__year=timezone.now().year, publish_date__week=week).count()
    else:
        return 0


@register.simple_tag(name='total_articles_today')
def total_daily_posts(date: Optional[timezone.datetime] = None) -> int:
    if not date:
        return Article.published.filter(publish_date__year=timezone.now().year,
                                        publish_date__month=timezone.now().month,
                                        publish_date__day=timezone.now().day).count()
    else:
        return Article.published.filter(publish_date__year=date.year, publish_date__month=date.month,
                                        publish_date__day=date.day).count()


@register.inclusion_tag('blog/latest.html')
def show_recent_articles(count=5):
    recent_articles = Article.published.order_by('-publish_date')[:count]
    return {'recent_articles': recent_articles}


@register.inclusion_tag('blog/latest.html')
def show_top_categories(count=5):
    categories = Categories.objects.annotate(
        num_articles=Count('article', filter=Q(article__is_published=True))).order_by('-num_articles')[:count]
    return {'categories': categories}


@register.simple_tag
def get_most_commented_posts(count=5):
    return Article.published.annotate(total_comments=Count('comments')).order_by('-total_comments')[:count]


@register.inclusion_tag('blog/latest.html')
def show_most_used_tags(count=5):
    """Return the most used tags i.e. tags common to all posts in descending order of count"""
    tags = Tag.objects.annotate(
        num_articles=Count('taggit_taggeditem_items__tag_id')).order_by('-num_articles')[:count]
    return {'tags': tags}


@register.filter(name='markdown_filter')
def markdown_format(text):
    return mark_safe(markdown.markdown(text))
