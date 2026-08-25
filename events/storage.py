from django.conf import settings
from django.core.files.storage import FileSystemStorage


def gallery_staging_storage():
    """Keep unconfirmed uploads on local disk, never in Cloudinary."""
    return FileSystemStorage(location=settings.OEF_GALLERY_STAGING_ROOT)
