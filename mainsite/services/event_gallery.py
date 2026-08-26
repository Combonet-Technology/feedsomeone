import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional

import cloudinary
import cloudinary.api
import cloudinary.uploader
from cloudinary import Search
from cloudinary.utils import cloudinary_url
from django.conf import settings

from utils.cloudinary_paths import (cloudinary_environment_tag,
                                    cloudinary_folder,
                                    normalise_cloudinary_segment)

logger = logging.getLogger(__name__)
MAX_CLOUDINARY_TAG_PUBLIC_IDS = 1000
MAX_CLOUDINARY_DELETE_PUBLIC_IDS = 100


@dataclass(frozen=True)
class GalleryAsset:
    asset_id: str
    public_id: str
    url: str
    thumbnail_url: str
    width: Optional[int]
    height: Optional[int]
    alt: str
    caption: str
    tags: tuple


def configure_cloudinary():
    values = getattr(settings, 'CLOUDINARY_STORAGE', {})
    required = ('CLOUD_NAME', 'API_KEY', 'API_SECRET')
    if not all(values.get(key) for key in required):
        return False
    cloudinary.config(
        cloud_name=values['CLOUD_NAME'], api_key=values['API_KEY'],
        api_secret=values['API_SECRET'], secure=True,
    )
    return True


def _search_resources(event, *, page_size=100, next_cursor=None):
    if not configure_cloudinary():
        raise RuntimeError('Cloudinary credentials are incomplete.')
    tags = [event.gallery_tag]
    if not getattr(settings, 'OEF_CLOUDINARY_LEGACY_GALLERY_FALLBACK', False):
        tags.append(cloudinary_environment_tag())
    expression = 'resource_type:image ' + ''.join(f'AND tags={tag} ' for tag in tags)
    query = (
        Search().expression(expression.strip()).with_field('context')
        .with_field('tags').sort_by('created_at', 'desc')
        .max_results(min(max(int(page_size), 1), 500))
    )
    if next_cursor:
        query = query.next_cursor(next_cursor)
    return query.execute()


def get_gallery_assets(event) -> List[GalleryAsset]:
    if (
        not event or not event.gallery_tag or not event.gallery_is_public
        or not getattr(settings, 'CLOUDINARY_GALLERY_ENABLED', False)
    ):
        return []
    from events.models import (EventGalleryImage,
                               event_image_effectively_public_q)

    records = EventGalleryImage.objects.filter(
        event_id=event.pk,
    ).filter(event_image_effectively_public_q()).order_by('-created_at', '-pk')
    return [
        _normalise_asset({
            'asset_id': record.asset_id,
            'public_id': record.public_id,
            'type': 'upload',
            'width': record.width,
            'height': record.height,
            'context': {'alt': record.alt_text, 'caption': ''},
            'tags': record.tags,
        }, event.title or 'OEF event')
        for record in records
    ]


def get_admin_gallery_page(event, *, next_cursor=None, page_size=100):
    response = _search_resources(
        event, page_size=page_size, next_cursor=next_cursor,
    )
    return {
        'assets': [_normalise_asset(item, event.title or 'OEF event') for item in response.get('resources', [])],
        'next_cursor': response.get('next_cursor'),
    }


def upload_event_image(event, uploaded_file, *, alt_text='', caption='', tags=()):
    from blog.media import validate_editorial_image

    alt_text = (alt_text or '').strip() or f'{event.title or "OEF event"} photograph'
    validate_editorial_image(uploaded_file, max_bytes=settings.OEF_EVENT_MEDIA_MAX_BYTES)
    user_tags = {
        normalise_cloudinary_segment(tag)[:96]
        for tag in tags if str(tag).strip()
    }
    mandatory_tags = {
        event.gallery_tag, cloudinary_environment_tag(),
        'oef-event-gallery',
    }
    response = cloudinary.uploader.upload(
        uploaded_file, resource_type='image', type='upload',
        folder=cloudinary_folder('events', event.gallery_tag),
        tags=sorted(mandatory_tags | user_tags),
        context={'alt': alt_text[:255], 'caption': (caption or '').strip()[:500]},
        use_filename=True, unique_filename=True, overwrite=False,
        quality_analysis=True,
    )
    return _normalise_asset(response, event.title or 'OEF event')


def gallery_user_tags(event, tags):
    """Return only editor-supplied tags for the database index."""
    reserved = {
        event.gallery_tag, cloudinary_environment_tag(), 'oef-event-gallery',
        settings.CLOUDINARY_GALLERY_PUBLICATION_TAG,
    }
    return sorted({str(tag) for tag in tags if str(tag) and str(tag) not in reserved})


def add_publication_tag(public_ids):
    """Mirror database publication to Cloudinary in one bounded bulk request."""
    public_ids = list(dict.fromkeys(str(value) for value in public_ids if value))
    if not public_ids:
        return {'public_ids': []}
    if len(public_ids) > MAX_CLOUDINARY_TAG_PUBLIC_IDS:
        raise ValueError(
            f'Cloudinary accepts at most {MAX_CLOUDINARY_TAG_PUBLIC_IDS} assets per tag request.'
        )
    if not configure_cloudinary():
        raise RuntimeError('Cloudinary credentials are incomplete.')
    return cloudinary.uploader.add_tag(
        settings.CLOUDINARY_GALLERY_PUBLICATION_TAG,
        public_ids,
        resource_type='image',
        type='upload',
    )


def remove_publication_tag(public_ids):
    """Remove the publication mirror tag in one bounded bulk request."""
    public_ids = list(dict.fromkeys(str(value) for value in public_ids if value))
    if not public_ids:
        return {'public_ids': []}
    if len(public_ids) > MAX_CLOUDINARY_TAG_PUBLIC_IDS:
        raise ValueError(
            f'Cloudinary accepts at most {MAX_CLOUDINARY_TAG_PUBLIC_IDS} assets per tag request.'
        )
    if not configure_cloudinary():
        raise RuntimeError('Cloudinary credentials are incomplete.')
    return cloudinary.uploader.remove_tag(
        settings.CLOUDINARY_GALLERY_PUBLICATION_TAG,
        public_ids,
        resource_type='image',
        type='upload',
    )


def _find_event_asset(event, public_id):
    cursor = None
    while True:
        page = get_admin_gallery_page(event, next_cursor=cursor, page_size=500)
        asset = next(
            (item for item in page['assets'] if item.public_id == public_id),
            None,
        )
        if asset or not page['next_cursor']:
            return asset
        cursor = page['next_cursor']


def update_event_image_metadata(
    event, public_id, *, alt_text='', caption='', tags=(), is_public=False,
):
    asset = _find_event_asset(event, public_id)
    if not asset:
        raise ValueError('That image does not belong to this event.')
    user_tags = {
        normalise_cloudinary_segment(tag)[:96]
        for tag in tags if str(tag).strip()
    }
    mandatory_tags = {
        event.gallery_tag, cloudinary_environment_tag(), 'oef-event-gallery',
    }
    if is_public:
        mandatory_tags.add(settings.CLOUDINARY_GALLERY_PUBLICATION_TAG)
    context = {
        'alt': (alt_text or '').strip()[:255],
        'caption': (caption or '').strip()[:500],
    }
    response = cloudinary.uploader.explicit(
        public_id, resource_type='image', type='upload',
        tags=sorted(mandatory_tags | user_tags), context=context,
    )
    return _normalise_asset(response, event.title or 'OEF event')


def delete_event_image(event, public_id):
    asset = _find_event_asset(event, public_id)
    if not asset:
        raise ValueError('That image does not belong to this event.')
    result = cloudinary.uploader.destroy(
        public_id, resource_type='image', type='upload', invalidate=True,
    )
    if result.get('result') not in ('ok', 'not found'):
        raise RuntimeError('Cloudinary did not delete the image.')
    return result


def delete_event_images(public_ids):
    """Delete known database-indexed images using Cloudinary's bulk API."""
    public_ids = list(dict.fromkeys(str(value) for value in public_ids if value))
    if not public_ids:
        return set(), {}
    if not configure_cloudinary():
        raise RuntimeError('Cloudinary credentials are incomplete.')

    batches = [
        public_ids[offset:offset + MAX_CLOUDINARY_DELETE_PUBLIC_IDS]
        for offset in range(0, len(public_ids), MAX_CLOUDINARY_DELETE_PUBLIC_IDS)
    ]

    def delete_batch(batch):
        try:
            response = cloudinary.api.delete_resources(
                batch, resource_type='image', type='upload', invalidate=True,
            )
        except Exception as exc:
            return set(), {public_id: str(exc) for public_id in batch}
        statuses = response.get('deleted') or {}
        batch_deleted = set()
        batch_failed = {}
        for public_id in batch:
            status = statuses.get(public_id)
            if status in ('deleted', 'not_found', 'not found'):
                batch_deleted.add(public_id)
            else:
                batch_failed[public_id] = status or 'unknown'
        return batch_deleted, batch_failed

    deleted = set()
    failed = {}
    with ThreadPoolExecutor(max_workers=min(4, len(batches))) as executor:
        futures = [executor.submit(delete_batch, batch) for batch in batches]
        for future in as_completed(futures):
            batch_deleted, batch_failed = future.result()
            deleted.update(batch_deleted)
            failed.update(batch_failed)
    return deleted, failed


def _normalise_asset(resource: Dict[str, object], event_title: str) -> GalleryAsset:
    public_id = str(resource['public_id'])
    delivery_type = str(resource.get('type', 'upload'))
    context = resource.get('context') or {}
    custom = context.get('custom', context) if isinstance(context, dict) else {}
    alt = str(custom.get('alt') or f'{event_title} outreach photograph')
    caption = str(custom.get('caption') or '')
    url, _ = cloudinary_url(
        public_id, secure=True, type=delivery_type, width=1600, height=1200,
        crop='limit', fetch_format='auto', quality='auto', dpr='auto',
    )
    thumbnail_url, _ = cloudinary_url(
        public_id, secure=True, type=delivery_type, width=640, height=480,
        crop='fill', gravity='auto', fetch_format='auto', quality='auto', dpr='auto',
    )
    return GalleryAsset(
        asset_id=str(resource.get('asset_id') or ''), public_id=public_id,
        url=url, thumbnail_url=thumbnail_url, width=resource.get('width'),
        height=resource.get('height'), alt=alt, caption=caption,
        tags=tuple(resource.get('tags') or ()),
    )
