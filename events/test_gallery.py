from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from events.models import Events
from mainsite.services.event_gallery import GalleryAsset


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

    def test_event_absolute_url_matches_detail_route(self):
        self.assertEqual(
            self.event.get_absolute_url(),
            reverse(
                'event-details',
                kwargs={'pk': self.event.pk, 'slug': self.event.event_slug},
            ),
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
        self.assertNotContains(response, 'Impact in Action')
        self.assertNotContains(response, 'Programme Record')
        self.assertNotContains(response, 'slider-area2')
        self.assertContains(response, 'oef-impact-detail-section')
        self.assertNotContains(response, 'consent and privacy review')
        get_assets.assert_called_once_with(self.event)

    @patch('events.views.get_gallery_assets')
    def test_event_gallery_uses_preview_and_scrollable_thumbnail_navigation(self, get_assets):
        get_assets.return_value = [
            GalleryAsset(
                asset_id=f'asset-{index}', public_id=f'events/photo-{index}',
                url=f'https://example.com/photo-{index}.jpg',
                thumbnail_url=f'https://example.com/thumb-{index}.jpg',
                width=1200, height=800, alt=f'Outreach photograph {index}',
                caption='', tags=(),
            )
            for index in range(12)
        ]

        response = self.client.get(
            reverse(
                'event-details',
                kwargs={'pk': self.event.pk, 'slug': self.event.event_slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'View images (12)')
        self.assertContains(response, 'data-gallery-preview')
        self.assertContains(response, 'data-active-index="0"')
        self.assertContains(response, 'data-gallery-previous')
        self.assertContains(response, 'data-gallery-next')
        self.assertContains(response, 'data-index="', count=12)
        self.assertContains(response, 'data-gallery-lightbox-link', count=12)
        self.assertContains(response, 'data-index="10"')
        self.assertContains(response, '1 / 12')
        self.assertContains(response, 'events/js/event-gallery-carousel.js?v=2')
        self.assertContains(response, 'events/css/event-gallery-carousel.css?v=2')
