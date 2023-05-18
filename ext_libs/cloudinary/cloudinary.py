from abc import ABC, abstractmethod
from typing import List, Optional, Union

import cloudinary
from cloudinary.uploader import upload
from cloudinary.utils import api_sign_request, cloudinary_url
from django.conf import settings

default_transformation = {
    'profile_pic': [dict(height=95, width=95, crop="thumb", gravity="face", radius=20),
                    dict(angle=10), ],
    'thumbnail': [
        dict(height=95, width=95, crop="thumb", gravity="face", effect="sepia", radius=20)],
    'article_img': [
        dict(height=95, width=95, crop="thumb", gravity="face", effect="sepia", radius=20)],
}


class UploaderHandler(ABC):
    @abstractmethod
    def upload(self, *args, **kwargs) -> str:
        """upload a single file - image, video, whatever"""

    def upload_multiple(self, *args, **kwargs):
        """upload multiple files at once, set tags, unique_filename=False,
        overwrite=False, type=authenticted, usefilemae=True"""

    def get_images(self, *args, **kwargs):
        """get all authenticated images that matches filter by tags, url, folder or any other
        method available in the API, apply transformations to the downloaded images
        kwargs = tags: str = None, transformation: str = None, folder: str = None"""


class CloudinaryHandler(UploaderHandler):
    def __init__(self):
        self.cloudinary = cloudinary.config(**settings.CLOUDINARY_STORAGE)

    def upload(self, file: Union[bytes, str], tags: Optional[Union[List[str], str]],
               folder: Optional[str] = None, res_type: str = 'image') -> str:
        """Upload single file to Cloudinary storage"""
        upload_params = {
            'file': file,
            'unique_filename': False,
            'overwrite': True,
            'tags': tags,
            'type': 'authenticated',
            'use_filename': True,
            'folder': folder,
            'resource_type': res_type
        }
        params_to_sign = cloudinary.utils.build_upload_params(**upload_params)
        params_to_sign = {k: v for k, v in params_to_sign.items() if v is not None}  # Filter out None values
        api_secret = settings.CLOUDINARY_STORAGE.get('API_SECRET')
        signature = api_sign_request(params_to_sign, api_secret)

        upload_params['signature'] = signature

        response = upload(**upload_params)

        srcURL, _ = cloudinary_url(
            response['public_id'],
            width=100,
            height=150,
            crop="fill"
        )
        print("****2. Upload an image****\nDelivery URL: ", srcURL, "\n")
        return srcURL

    def get_image(self, preset, tags: str = None, transformation: str = None, folder: str = None):
        """get all authenticated images that matches filter by tags, url, folder or any other
        method available in the API, apply transformations to the downloaded images"""

        if not transformation:
            transformation = default_transformation[preset]

    def upload_multiple(self, files: List[Union[bytes, str]], tags: Optional[Union[List[str], str]],
                        folder: Optional[str] = None, res_type: str = 'image') -> List[str]:
        """Upload multiple files to Cloudinary storage"""
        uploaded_urls = []
        for file in files:
            uploaded_url = self.upload(file, tags, folder, res_type)
            uploaded_urls.append(uploaded_url)
        return uploaded_urls

    def get_images(self, tags: Optional[str] = None, transformation: Optional[str] = None,
                   folder: Optional[str] = None) -> List[str]:
        """Get a list of URLs for images that match the specified filters and transformations"""
        search_params = {
            'tags': tags,
            'transformation': transformation,
            'folder': folder
        }
        search_params = {k: v for k, v in search_params.items() if v is not None}  # Filter out None values
        search_response = cloudinary.Search().expression('resource_type:image').with_params(**search_params).execute()
        images = []
        for item in search_response['resources']:
            srcURL, _ = cloudinary_url(
                item['public_id'],
                width=100,
                height=150,
                crop="fill"
            )
            images.append(srcURL)
        return images
