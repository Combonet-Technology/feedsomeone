from pathlib import Path
from urllib.parse import unquote, urlparse

import cloudinary.uploader
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from blog.models import MediaAsset
from utils.cloudinary_paths import (cloudinary_environment_tag,
                                    cloudinary_folder)

ALLOWED_IMAGE_FORMATS = {
    'JPEG': ('jpg', 'jpeg'),
    'PNG': ('png',),
    'WEBP': ('webp',),
}
MAX_IMAGE_PIXELS = 40_000_000


def editorial_public_id_from_url(value):
    """Return an exact current-account/current-environment editorial public ID."""
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

    folder_parts = cloudinary_folder('editorial').split('/')
    upload_parts = parts[3:]
    try:
        folder_index = next(
            index
            for index in range(len(upload_parts) - len(folder_parts) + 1)
            if upload_parts[index:index + len(folder_parts)] == folder_parts
        )
    except StopIteration:
        return None

    public_parts = upload_parts[folder_index:]
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
