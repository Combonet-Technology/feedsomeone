import re
from html.parser import HTMLParser

from django.core.exceptions import ValidationError
from django.utils.html import strip_tags


class _ImageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'img':
            self.images.append(dict(attrs))


def image_references(html):
    parser = _ImageParser()
    parser.feed(html or '')
    return parser.images


def validate_article_content(html):
    if not strip_tags(html or '').strip() and not image_references(html):
        raise ValidationError('Article content cannot be empty.')

    from blog.media import managed_media_public_id_from_url

    errors = []
    for index, image in enumerate(image_references(html), start=1):
        source = (image.get('src') or '').strip()
        alt_text = (image.get('alt') or '').strip()
        if not alt_text:
            errors.append(f'Image {index} requires alternative text.')
        if managed_media_public_id_from_url(source) is None:
            errors.append(f'Image {index} must use an approved secure OEF media URL.')

    if errors:
        raise ValidationError(errors)


def image_urls(html):
    return {
        image.get('src').strip()
        for image in image_references(html)
        if image.get('src')
    }


_FIGURE_RE = re.compile(r'<figure\b[^>]*>.*?</figure>', re.IGNORECASE | re.DOTALL)


def remove_incomplete_figures(html):
    """Remove empty figure placeholders created when an insert dialog is cancelled."""
    def keep_or_remove(match):
        fragment = match.group(0)
        images = image_references(fragment)
        if images and all(not (image.get('src') or '').strip() for image in images):
            return ''
        return fragment

    return _FIGURE_RE.sub(keep_or_remove, html or '')
