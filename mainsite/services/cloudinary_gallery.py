import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import cloudinary
from cloudinary import Search
from cloudinary.utils import cloudinary_url
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GalleryAsset:
    public_id: str
    url: str
    thumbnail_url: str
    width: Optional[int]
    height: Optional[int]
    alt: str


def get_gallery_definition(slug: str) -> Optional[Dict[str, str]]:
    return getattr(settings, 'CLOUDINARY_GALLERIES', {}).get(slug)


def resolve_event_gallery_slug(event_slug: str, title: str = '') -> Optional[str]:
    """Map legacy event slugs/titles to one of the allow-listed galleries."""
    candidates = f'{event_slug} {title}'.lower()
    if 'feed-someone-1.0' in candidates or 'feed-someone-1-0' in candidates:
        return 'feed-someone-1.0'
    if 'feed-someone-2.0' in candidates or 'feed-someone-2-0' in candidates:
        return 'feed-someone-2.0'
    return event_slug if get_gallery_definition(event_slug) else None


def get_gallery_assets(slug: str) -> List[GalleryAsset]:
    """Return public delivery URLs for one allow-listed historical event."""
    gallery = get_gallery_definition(slug)
    if not gallery or not getattr(settings, 'CLOUDINARY_GALLERY_ENABLED', False):
        return []

    cloudinary_settings = getattr(settings, 'CLOUDINARY_STORAGE', {})
    required = ('CLOUD_NAME', 'API_KEY', 'API_SECRET')
    if not all(cloudinary_settings.get(key) for key in required):
        logger.warning('Cloudinary gallery is enabled but credentials are incomplete.')
        return []

    publication_tag = settings.CLOUDINARY_GALLERY_PUBLICATION_TAG
    cache_key = f'oef:gallery:{gallery["tag"]}:{publication_tag}'
    cached_assets = cache.get(cache_key)
    if cached_assets is not None:
        return cached_assets

    try:
        cloudinary.config(
            cloud_name=cloudinary_settings['CLOUD_NAME'],
            api_key=cloudinary_settings['API_KEY'],
            api_secret=cloudinary_settings['API_SECRET'],
            secure=True,
        )
        response = (
            Search()
            .expression(
                f'resource_type:image AND tags={gallery["tag"]} '
                f'AND tags={publication_tag}'
            )
            .sort_by('public_id', 'asc')
            .max_results(100)
            .execute()
        )
    except Exception:
        logger.exception('Unable to load Cloudinary gallery %s.', slug)
        return []

    assets = [_normalise_asset(item, gallery['title']) for item in response.get('resources', [])]
    cache.set(
        cache_key,
        assets,
        getattr(settings, 'CLOUDINARY_GALLERY_CACHE_SECONDS', 900),
    )
    return assets


def _normalise_asset(resource: Dict[str, object], event_title: str) -> GalleryAsset:
    public_id = str(resource['public_id'])
    delivery_type = str(resource.get('type', 'upload'))
    url, _ = cloudinary_url(
        public_id,
        secure=True,
        type=delivery_type,
        width=1600,
        height=1200,
        crop='limit',
        fetch_format='auto',
        quality='auto',
    )
    thumbnail_url, _ = cloudinary_url(
        public_id,
        secure=True,
        type=delivery_type,
        width=640,
        height=480,
        crop='fill',
        gravity='auto',
        fetch_format='auto',
        quality='auto',
    )
    return GalleryAsset(
        public_id=public_id,
        url=url,
        thumbnail_url=thumbnail_url,
        width=resource.get('width'),
        height=resource.get('height'),
        alt=f'{event_title} outreach photograph',
    )
