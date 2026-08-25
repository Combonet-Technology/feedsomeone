import re

from django.conf import settings

_UNSAFE_SEGMENT = re.compile(r'[^a-z0-9_-]+')


def normalise_cloudinary_segment(value):
    """Return a predictable Cloudinary folder/tag segment."""
    segment = _UNSAFE_SEGMENT.sub('-', str(value or '').strip().lower()).strip('-_')
    return segment or 'local'


def cloudinary_environment():
    return normalise_cloudinary_segment(
        getattr(settings, 'OEF_CLOUDINARY_ENVIRONMENT', 'local')
    )


def cloudinary_folder(*parts):
    root = normalise_cloudinary_segment(
        getattr(settings, 'OEF_CLOUDINARY_ROOT_FOLDER', 'oef')
    )
    segments = [root, cloudinary_environment()]
    segments.extend(normalise_cloudinary_segment(part) for part in parts if part)
    return '/'.join(segments)


def cloudinary_environment_tag():
    return f'oef-environment-{cloudinary_environment()}'
