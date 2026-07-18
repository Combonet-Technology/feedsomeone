import os
import time

import cloudinary.uploader
import cloudinary.utils
from cloudinary_storage.storage import RawMediaCloudinaryStorage
from django.conf import settings
from django.core.files.storage import (FileSystemStorage, Storage,
                                       default_storage)
from django.utils.deconstruct import deconstructible

PRIVATE_CV_PREFIX = 'vacancy_applications/private_cv/'
CLOUDINARY_MEDIA_PREFIX = 'media/'


def _normalise_private_cv_name(name):
    normalised_name = str(name).replace('\\', '/')
    prefixed_private_cv = f'{CLOUDINARY_MEDIA_PREFIX}{PRIVATE_CV_PREFIX}'
    if normalised_name.startswith(prefixed_private_cv):
        return normalised_name[len(CLOUDINARY_MEDIA_PREFIX):]
    return normalised_name


class AuthenticatedRawCloudinaryStorage(RawMediaCloudinaryStorage):
    def _upload(self, name, content):
        return cloudinary.uploader.upload(
            content,
            public_id=name,
            resource_type='raw',
            type='authenticated',
            overwrite=False,
            tags=self.TAG,
        )

    def _get_url(self, name):
        name = self._prepend_prefix(name)
        _, extension = os.path.splitext(name)
        return cloudinary.utils.private_download_url(
            name,
            extension.lstrip('.'),
            resource_type='raw',
            type='authenticated',
            attachment=True,
            expires_at=int(time.time()) + settings.VACANCY_CV_LINK_TTL_SECONDS,
        )

    def delete(self, name):
        response = cloudinary.uploader.destroy(
            self._prepend_prefix(name),
            invalidate=True,
            resource_type='raw',
            type='authenticated',
        )
        return response['result'] == 'ok'


@deconstructible
class VacancyCVStorage(Storage):
    @staticmethod
    def _cloudinary_is_configured():
        configuration = getattr(settings, 'CLOUDINARY_STORAGE', {})
        return all(
            configuration.get(key)
            for key in ('CLOUD_NAME', 'API_KEY', 'API_SECRET')
        )

    def _backend(self, name):
        if _normalise_private_cv_name(name).startswith(PRIVATE_CV_PREFIX):
            if self._cloudinary_is_configured():
                return AuthenticatedRawCloudinaryStorage()
            return FileSystemStorage(
                location=settings.MEDIA_ROOT,
                base_url=settings.MEDIA_URL,
            )
        return default_storage

    def _open(self, name, mode='rb'):
        backend_name = _normalise_private_cv_name(name)
        return self._backend(backend_name).open(backend_name, mode)

    def _save(self, name, content):
        backend_name = _normalise_private_cv_name(name)
        saved_name = self._backend(backend_name).save(backend_name, content)
        return _normalise_private_cv_name(saved_name)

    def delete(self, name):
        backend_name = _normalise_private_cv_name(name)
        return self._backend(backend_name).delete(backend_name)

    def exists(self, name):
        backend_name = _normalise_private_cv_name(name)
        return self._backend(backend_name).exists(backend_name)

    def size(self, name):
        backend_name = _normalise_private_cv_name(name)
        return self._backend(backend_name).size(backend_name)

    def url(self, name):
        backend_name = _normalise_private_cv_name(name)
        return self._backend(backend_name).url(backend_name)
