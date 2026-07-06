from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from events.models import Events


@override_settings(CLOUDINARY_GALLERY_ENABLED=True)
class EventDetailGalleryTests(TestCase):
    def setUp(self):
        self.event = Events.objects.create(
            title='Feed Someone 1.0',
            event_date=date(2019, 12, 27),
            event_slug='feed-someone-1-0',
            location='Akure, Ondo State',
            feature_img='event_feature_img/placeholder.jpg',
            time='11:00',
            content='The first Feed Someone outreach.',
        )

    @patch('events.views.get_gallery_assets', return_value=[])
    def test_event_detail_uses_the_matching_gallery_tag(self, get_assets):
        response = self.client.get(
            reverse(
                'event-details',
                kwargs={'pk': self.event.pk, 'slug': self.event.event_slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Feed Someone 1.0 gallery')
        get_assets.assert_called_once_with('feed-someone-1.0')
