import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import cloudinary.uploader
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from PIL import Image, UnidentifiedImageError

from blog.models import Article, MediaAsset
from utils.cloudinary_paths import (cloudinary_environment_tag,
                                    cloudinary_folder)

ALLOWED_IMAGE_FORMATS = {
    'JPEG': ('jpg', 'jpeg'),
    'PNG': ('png',),
    'WEBP': ('webp',),
}
MAX_IMAGE_PIXELS = 40_000_000
_CLOUDINARY_VERSION = re.compile(r'^v\d+$')
_CLOUDINARY_TRANSFORMATION = re.compile(r'^[A-Za-z]{1,8}_.+$')


def _is_cloudinary_delivery_prefix(parts):
    """Accept only Cloudinary transformation/version segments before a public ID."""
    parts = list(parts)
    if parts and _CLOUDINARY_VERSION.fullmatch(parts[-1]):
        parts.pop()
    return all(
        segment and all(
            _CLOUDINARY_TRANSFORMATION.fullmatch(component)
            for component in segment.split(',')
        )
        for segment in parts
    )


def editorial_public_id_from_url(value):
    """Return an exact current-account/current-environment editorial public ID."""
    public_id = managed_media_public_id_from_url(value)
    if public_id and public_id.startswith(f'{cloudinary_folder("editorial")}/'):
        return public_id
    return None


def managed_media_public_id_from_url(value):
    """Return an exact current-environment editorial or event-media public ID."""
    parsed = urlparse(value or '')
    if (
        parsed.scheme != 'https'
        or parsed.hostname not in settings.OEF_EDITORIAL_IMAGE_HOSTS
    ):
        return None

    cloud_name = (getattr(settings, 'CLOUDINARY_STORAGE', {}) or {}).get('CLOUD_NAME')
    if not cloud_name:
        return None

    parts = [part for part in unquote(parsed.path).split('/') if part]
    if len(parts) < 5 or parts[:3] != [cloud_name, 'image', 'upload']:
        return None

    upload_parts = parts[3:]
    allowed_folders = (
        cloudinary_folder('editorial').split('/'),
        cloudinary_folder('events').split('/'),
    )
    public_parts = None
    for candidate in allowed_folders:
        for index in range(len(upload_parts) - len(candidate) + 1):
            if (
                upload_parts[index:index + len(candidate)] == candidate
                and _is_cloudinary_delivery_prefix(upload_parts[:index])
            ):
                public_parts = upload_parts[index:]
                folder_parts = candidate
                break
        if public_parts is not None:
            break
    if public_parts is None:
        return None

    if len(public_parts) <= len(folder_parts):
        return None
    if public_parts[-1].lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.avif')):
        public_parts[-1] = public_parts[-1].rsplit('.', 1)[0]
    if not public_parts[-1]:
        return None
    return '/'.join(public_parts)


def editorial_public_ids_from_urls(urls):
    """Extract exact current-account/current-environment editorial public IDs."""
    return {
        public_id
        for value in urls
        if (public_id := editorial_public_id_from_url(value))
    }


def managed_media_public_ids_from_urls(urls):
    """Extract exact managed editorial/event public IDs from Cloudinary URLs."""
    return {
        public_id
        for value in urls
        if (public_id := managed_media_public_id_from_url(value))
    }


@transaction.atomic
def adopt_event_gallery_image(image, user):
    """Index an event image for editorial reuse without copying its Cloudinary binary."""
    from events.models import (EventGalleryImage, Events,
                               is_event_image_effectively_public)

    Events.objects.select_for_update().get(pk=image.event_id)
    image = (
        EventGalleryImage.objects.select_for_update().select_related('event')
        .filter(pk=image.pk).first()
    )
    if not image:
        raise ValidationError('This event image is no longer available.')
    if not image.public_id.startswith(f'{cloudinary_folder("events")}/'):
        raise ValidationError('This image is outside the managed event-media folder.')
    if not is_event_image_effectively_public(image):
        raise ValidationError('This event image is not available for public editorial use.')

    existing = MediaAsset.objects.filter(public_id=image.public_id).first()
    if existing:
        if existing.source_event_image_id is None:
            existing.source_event_image = image
            existing.save(update_fields=('source_event_image',))
        return existing, False

    suffix = Path(urlparse(image.secure_url).path).suffix.lstrip('.').lower()
    image_format = suffix or Path(image.original_filename).suffix.lstrip('.').lower() or 'jpg'
    asset, created = MediaAsset.objects.get_or_create(
        public_id=image.public_id,
        defaults={
            'asset_id': image.asset_id or f'event-gallery-{image.pk}',
            'secure_url': image.secure_url,
            'original_filename': image.original_filename or Path(image.public_id).name,
            'format': image_format[:20],
            'width': image.width or 1,
            'height': image.height or 1,
            'bytes': 0,
            'alt_text': image.alt_text or f'Photograph from {image.event.title}',
            'caption': '',
            'uploaded_by': user,
            'approved_for_publication': image.is_public,
            'source_event_image': image,
        },
    )
    return asset, created


def event_image_has_editorial_usage(image):
    """Return whether an adopted event binary is referenced by editorial content."""
    return image.pk in event_image_ids_with_editorial_usage([image.pk])


def event_image_ids_with_editorial_usage(image_ids):
    """Return source IDs used by drafts or revisions in a bounded query sequence."""
    image_ids = set(image_ids)
    if not image_ids:
        return set()
    assets = list(MediaAsset.objects.filter(
        source_event_image_id__in=image_ids,
    ).values('source_event_image_id', 'public_id'))
    if not assets:
        return set()
    used = set(MediaAsset.objects.filter(
        source_event_image_id__in=image_ids,
    ).filter(
        Q(featured_articles__isnull=False)
        | Q(article_revisions__isnull=False)
    ).values_list('source_event_image_id', flat=True).distinct())
    public_id_to_source = {
        asset['public_id']: asset['source_event_image_id'] for asset in assets
    }
    content_query = Q()
    for public_id in public_id_to_source:
        content_query |= Q(article_content__contains=public_id)
    if content_query:
        for content in Article.objects.filter(content_query).values_list(
            'article_content', flat=True,
        ):
            used.update(
                source_id for public_id, source_id in public_id_to_source.items()
                if public_id in content
            )
    return used


def event_image_has_live_editorial_usage(image):
    """Return whether a currently public article exposes the adopted binary."""
    return image.pk in event_image_ids_with_live_editorial_usage([image.pk])


def event_image_ids_with_live_editorial_usage(image_ids):
    """Find all selected sources used by live revisions in one query."""
    return set(MediaAsset.objects.filter(
        source_event_image_id__in=set(image_ids),
        article_revisions__published_articles__is_published=True,
        article_revisions__published_articles__is_deleted=False,
    ).values_list('source_event_image_id', flat=True).distinct())


def validate_event_images_can_be_made_private(images):
    image_ids = [image.pk for image in images]
    protected_ids = event_image_ids_with_live_editorial_usage(image_ids)
    if protected_ids:
        raise ValidationError(
            f'{len(protected_ids)} image(s) are used by published articles and cannot be made private. '
            'Remove or replace them in the published articles, then try again.'
        )


def remove_unused_event_adoption(image):
    """Remove an adoption record only when no article or revision depends on it."""
    asset = MediaAsset.objects.filter(source_event_image=image).first()
    if not asset:
        return
    if event_image_has_editorial_usage(image):
        raise ValidationError('This image is used by editorial content.')
    asset.delete()


def validate_editorial_image(uploaded_file, max_bytes=None):
    if not uploaded_file:
        raise ValidationError('Select an image to upload.')
    if uploaded_file.size > (max_bytes or settings.OEF_EDITORIAL_MEDIA_MAX_BYTES):
        raise ValidationError('The image exceeds the editorial upload size limit.')

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image_format = (image.format or '').upper()
        width, height = image.size
        image.verify()
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise ValidationError('The uploaded file is not a valid supported image.') from exc
    finally:
        uploaded_file.seek(0)

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError('Only JPEG, PNG and WebP images are supported.')
    if width * height > MAX_IMAGE_PIXELS:
        raise ValidationError('The image dimensions are too large.')
    return image_format.lower(), width, height


def upload_editorial_image(uploaded_file, user, alt_text, caption=''):
    alt_text = (alt_text or '').strip()
    caption = (caption or '').strip()
    if not alt_text:
        raise ValidationError('Alternative text is required.')
    image_format, width, height = validate_editorial_image(uploaded_file)

    response = cloudinary.uploader.upload(
        uploaded_file,
        resource_type='image',
        type='upload',
        folder=cloudinary_folder('editorial'),
        tags=['oef-editorial', 'editorial-staging', cloudinary_environment_tag()],
        use_filename=True,
        unique_filename=True,
        overwrite=False,
        quality_analysis=True,
    )
    try:
        secure_url = response['secure_url']
        if editorial_public_id_from_url(secure_url) != response.get('public_id'):
            raise ValidationError('The media provider returned an unapproved image URL.')
        return MediaAsset.objects.create(
            asset_id=response['asset_id'],
            public_id=response['public_id'],
            secure_url=secure_url,
            original_filename=Path(uploaded_file.name).name[:255],
            format=(response.get('format') or image_format)[:20],
            width=response.get('width') or width,
            height=response.get('height') or height,
            bytes=response.get('bytes') or uploaded_file.size,
            alt_text=alt_text[:255],
            caption=caption[:500],
            quality_score=(response.get('quality_analysis') or {}).get('focus'),
            uploaded_by=user,
        )
    except Exception:
        public_id = response.get('public_id')
        if public_id:
            cloudinary.uploader.destroy(public_id, resource_type='image', type='upload')
        raise
