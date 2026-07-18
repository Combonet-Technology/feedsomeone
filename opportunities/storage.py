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
        public_id, extension = os.path.splitext(name)
        return cloudinary.utils.private_download_url(
            public_id,
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
        if name.startswith(PRIVATE_CV_PREFIX):
            if self._cloudinary_is_configured():
                return AuthenticatedRawCloudinaryStorage()
            return FileSystemStorage(
                location=settings.MEDIA_ROOT,
                base_url=settings.MEDIA_URL,
            )
        return default_storage

    def _open(self, name, mode='rb'):
        return self._backend(name).open(name, mode)

    def _save(self, name, content):
        return self._backend(name).save(name, content)

    def delete(self, name):
        return self._backend(name).delete(name)

    def exists(self, name):
        return self._backend(name).exists(name)

    def size(self, name):
        return self._backend(name).size(name)

    def url(self, name):
        return self._backend(name).url(name)
