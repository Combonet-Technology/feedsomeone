from django.test import SimpleTestCase, override_settings

from utils.cloudinary_paths import (cloudinary_environment_tag,
                                    cloudinary_folder)


class CloudinaryPathTests(SimpleTestCase):
    @override_settings(OEF_CLOUDINARY_ROOT_FOLDER='OEF', OEF_CLOUDINARY_ENVIRONMENT='Local Test')
    def test_folder_and_tag_are_environment_scoped(self):
        self.assertEqual(
            cloudinary_folder('Event Galleries', 'Launch Day'),
            'oef/local-test/event-galleries/launch-day',
        )
        self.assertEqual(cloudinary_environment_tag(), 'oef-environment-local-test')
