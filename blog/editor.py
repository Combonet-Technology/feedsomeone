from django.conf import settings

ARTICLE_EDITOR_EXTENSIONS = {
    'Bold': True,
    'Italic': True,
    'Underline': True,
    'Strike': True,
    'Heading': {'levels': [2, 3, 4]},
    'BulletList': True,
    'OrderedList': True,
    'ListItem': True,
    'Blockquote': True,
    'HorizontalRule': True,
    'HardBreak': True,
    'Link': {
        'enableTarget': True,
        'protocols': ['http', 'https', 'mailto'],
    },
    'Image': True,
    'Caption': True,
    'Figure': {
    },
    'InlineImageUpload': {
        'uploadUrl': settings.OEF_EDITORIAL_MEDIA_UPLOAD_URL,
        'libraryUrl': settings.OEF_EDITORIAL_MEDIA_LIBRARY_URL,
        'maxFileSize': settings.OEF_EDITORIAL_MEDIA_MAX_BYTES,
        'allowedTypes': ['image/jpeg', 'image/png', 'image/webp'],
    },
    'History': True,
    'Typographic': True,
}
