import json

from django.utils.html import strip_tags
from django.utils.text import Truncator


def build_article_meta(request, article):
    """Build reusable, page-specific metadata for an article detail page."""
    description_source = article.public_excerpt or strip_tags(article.public_content)
    description = Truncator(' '.join(description_source.split())).chars(160)
    canonical_url = request.build_absolute_uri(article.get_absolute_url())
    image_url = request.build_absolute_uri(
        article.public_feature_image_url or '/static/img/logo/oef-logo.svg'
    )
    author_name = article.public_author.get_full_name() if article.public_author else 'OEF Editorial Team'

    structured_data = {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': article.public_title,
        'description': description,
        'datePublished': article.publish_date.isoformat(),
        'dateModified': article.public_modified_at.isoformat(),
        'mainEntityOfPage': canonical_url,
        'author': {
            '@type': 'Person',
            'name': author_name,
        },
        'publisher': {
            '@type': 'Organization',
            'name': 'Oluwafemi Ebenezer Foundation',
            'logo': {
                '@type': 'ImageObject',
                'url': request.build_absolute_uri('/static/img/logo/oef-logo.svg'),
            },
        },
    }
    structured_data['image'] = [image_url]

    structured_data_json = json.dumps(structured_data, ensure_ascii=False)
    structured_data_json = (
        structured_data_json
        .replace('&', '\\u0026')
        .replace('<', '\\u003c')
        .replace('>', '\\u003e')
    )

    return {
        'canonical_url': canonical_url,
        'description': description,
        'image_alt': article.public_title,
        'image_url': image_url,
        'structured_data': structured_data_json,
    }
