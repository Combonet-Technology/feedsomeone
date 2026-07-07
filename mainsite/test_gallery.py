from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from mainsite.services.cloudinary_gallery import (GalleryAsset,
                                                  get_gallery_assets,
                                                  resolve_event_gallery_slug)

GALLERIES = {
    'feed-someone-1.0': {
        'tag': 'feed-someone-1.0',
        'title': 'Feed Someone 1.0',
        'date': '27 December 2019',
        'location': 'Akure, Ondo State',
        'summary': 'Community relief.',
        'library_count': 25,
    },
    'feed-someone-2.0': {
        'tag': 'feed-someone-2.0',
        'title': 'Feed Someone 2.0',
        'date': 'December 2020',
        'location': 'Akure, Ondo State',
        'summary': 'Orphanage and community relief.',
        'library_count': 74,
    },
}


@override_settings(
    CLOUDINARY_GALLERY_ENABLED=True,
    CLOUDINARY_GALLERY_CACHE_SECONDS=900,
    CLOUDINARY_GALLERY_PUBLICATION_TAG='publication-approved',
    CLOUDINARY_GALLERIES=GALLERIES,
    CLOUDINARY_STORAGE={'CLOUD_NAME': 'test', 'API_KEY': 'key', 'API_SECRET': 'secret'},
)
class CloudinaryGalleryServiceTests(SimpleTestCase):
    def setUp(self):
        self.search = Mock()
        self.search.expression.return_value = self.search
        self.search.sort_by.return_value = self.search
        self.search.max_results.return_value = self.search
        self.search.execute.return_value = {
            'resources': [
                {'public_id': 'feed-someone/photo-1', 'type': 'upload', 'width': 1200, 'height': 800}
            ]
        }

    @patch('mainsite.services.cloudinary_gallery.cloudinary_url')
    @patch('mainsite.services.cloudinary_gallery.Search')
    def test_fetches_only_the_allow_listed_event_tag(self, search_class, cloudinary_url):
        search_class.return_value = self.search
        cloudinary_url.side_effect = [
            ('https://example.com/photo.jpg', {}),
            ('https://example.com/thumb.jpg', {}),
        ]

        assets = get_gallery_assets('feed-someone-1.0')

        self.search.expression.assert_called_once_with(
            'resource_type:image AND tags=feed-someone-1.0 AND tags=publication-approved'
        )
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].thumbnail_url, 'https://example.com/thumb.jpg')
        self.assertEqual(assets[0].alt, 'Feed Someone 1.0 outreach photograph')

    def test_rejects_an_unknown_gallery_slug(self):
        self.assertEqual(get_gallery_assets('not-allowed'), [])

    def test_resolves_legacy_event_slug(self):
        self.assertEqual(
            resolve_event_gallery_slug('feed-someone-1-0'),
            'feed-someone-1.0',
        )


@override_settings(
    CLOUDINARY_GALLERY_ENABLED=True,
    CLOUDINARY_GALLERIES=GALLERIES,
)
class GalleryViewTests(SimpleTestCase):
    @patch('mainsite.views.get_gallery_assets')
    def test_selected_event_gallery_renders_cloudinary_assets(self, get_assets):
        get_assets.return_value = [
            GalleryAsset(
                public_id='photo-1',
                url='https://example.com/photo.jpg',
                thumbnail_url='https://example.com/thumb.jpg',
                width=1200,
                height=800,
                alt='Feed Someone 1.0 outreach photograph',
            )
        ]

        response = self.client.get(
            reverse('mainsite:gallery'),
            {'event': 'feed-someone-1.0'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Feed Someone 1.0')
        self.assertContains(response, 'OEF Evidence Gallery')
        self.assertContains(response, 'View programme records')
        self.assertContains(response, 'Read impact summary')
        self.assertContains(response, "OEF's media review workflow")
        self.assertContains(response, 'https://example.com/thumb.jpg')
        get_assets.assert_called_once_with('feed-someone-1.0')

    def test_unknown_event_does_not_trigger_a_cloudinary_query(self):
        with patch('mainsite.views.get_gallery_assets') as get_assets:
            response = self.client.get(reverse('mainsite:gallery'), {'event': 'unknown'})

        self.assertEqual(response.status_code, 200)
        get_assets.assert_not_called()
        self.assertContains(response, 'Choose an outreach above to view its approved evidence gallery')

    def test_impact_page_links_to_both_verified_galleries(self):
        response = self.client.get(reverse('mainsite:impact'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'event=feed-someone-1.0')
        self.assertContains(response, 'event=feed-someone-2.0')


@override_settings(CLOUDINARY_GALLERY_ENABLED=False, CLOUDINARY_GALLERIES=GALLERIES)
class GalleryPrivacyGateTests(SimpleTestCase):
    def test_disabled_gallery_explains_the_privacy_review(self):
        response = self.client.get(
            reverse('mainsite:gallery'),
            {'event': 'feed-someone-2.0'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'consent and privacy review')
