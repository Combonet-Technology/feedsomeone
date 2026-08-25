from datetime import date
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from events.models import EventGalleryImage, Events
from mainsite.services.event_gallery import (GalleryAsset, add_publication_tag,
                                             delete_event_images,
                                             get_gallery_assets,
                                             remove_publication_tag,
                                             update_event_image_metadata,
                                             upload_event_image)
from utils.cloudinary_paths import (cloudinary_environment_tag,
                                    cloudinary_folder)

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
    CLOUDINARY_GALLERY_PUBLICATION_TAG='publication-approved',
    CLOUDINARY_GALLERIES=GALLERIES,
    CLOUDINARY_STORAGE={'CLOUD_NAME': 'test', 'API_KEY': 'key', 'API_SECRET': 'secret'},
)
class CloudinaryGalleryServiceTests(TestCase):
    def setUp(self):
        self.search = Mock()
        self.search.expression.return_value = self.search
        self.search.with_field.return_value = self.search
        self.search.sort_by.return_value = self.search
        self.search.max_results.return_value = self.search
        self.search.execute.return_value = {
            'resources': [
                {'public_id': 'feed-someone/photo-1', 'type': 'upload', 'width': 1200, 'height': 800}
            ]
        }

    @patch('mainsite.services.event_gallery.cloudinary_url')
    @patch('mainsite.services.event_gallery.Search')
    def test_public_gallery_uses_only_database_approved_images(self, search_class, cloudinary_url):
        cloudinary_url.side_effect = [
            ('https://example.com/photo.jpg', {}),
            ('https://example.com/thumb.jpg', {}),
        ]
        event = Events.objects.create(
            title='Feed Someone 1.0', event_date=date(2019, 12, 27),
            event_slug='feed-someone-1-0', location='Akure',
            feature_img='event_feature_img/test.jpg', time='11:00',
            content='Community relief.', gallery_tag='feed-someone-1.0',
            gallery_is_public=True,
        )
        EventGalleryImage.objects.create(
            event=event, asset_id='asset-public', public_id='events/photo-public',
            secure_url='https://example.com/public.jpg', original_filename='public.jpg',
            width=1200, height=800, alt_text='Volunteers serving meals',
            tags=['volunteers'], is_public=True,
        )
        EventGalleryImage.objects.create(
            event=event, asset_id='asset-private', public_id='events/photo-private',
            secure_url='https://example.com/private.jpg', original_filename='private.jpg',
            is_public=False,
        )

        assets = get_gallery_assets(event)

        search_class.assert_not_called()
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].public_id, 'events/photo-public')
        self.assertEqual(assets[0].thumbnail_url, 'https://example.com/thumb.jpg')
        self.assertEqual(assets[0].alt, 'Volunteers serving meals')

    @patch('mainsite.services.event_gallery.Search')
    def test_event_level_database_gate_hides_approved_images(self, search_class):
        event = Events.objects.create(
            title='Private gallery event', event_date=date(2026, 1, 1),
            event_slug='private-gallery-event', location='Akure',
            feature_img='event_feature_img/test.jpg', time='11:00',
            content='Community relief.', gallery_tag='private-gallery-event',
            gallery_is_public=False,
        )
        EventGalleryImage.objects.create(
            event=event, asset_id='asset-public', public_id='events/hidden-photo',
            secure_url='https://example.com/hidden.jpg', original_filename='hidden.jpg',
            is_public=True,
        )

        self.assertEqual(get_gallery_assets(event), [])
        search_class.assert_not_called()

    def test_rejects_missing_event(self):
        self.assertEqual(get_gallery_assets(None), [])

    @patch('mainsite.services.event_gallery.cloudinary.uploader.add_tag')
    def test_publication_tag_is_added_in_one_bulk_request(self, add_tag):
        add_tag.return_value = {'public_ids': ['events/photo-1', 'events/photo-2']}

        add_publication_tag(['events/photo-1', 'events/photo-2'])

        add_tag.assert_called_once_with(
            'publication-approved',
            ['events/photo-1', 'events/photo-2'],
            resource_type='image', type='upload',
        )

    @patch('mainsite.services.event_gallery.cloudinary.uploader.add_tag')
    def test_publication_tag_rejects_more_than_cloudinary_limit(self, add_tag):
        with self.assertRaisesMessage(ValueError, 'at most 1000 assets'):
            add_publication_tag([f'events/photo-{index}' for index in range(1001)])

        add_tag.assert_not_called()

    @patch('mainsite.services.event_gallery.cloudinary.uploader.remove_tag')
    def test_private_action_removes_publication_tag_in_one_request(self, remove_tag):
        public_ids = ['events/photo-1', 'events/photo-2']

        remove_publication_tag(public_ids)

        remove_tag.assert_called_once_with(
            settings.CLOUDINARY_GALLERY_PUBLICATION_TAG,
            public_ids,
            resource_type='image', type='upload',
        )

    @patch('mainsite.services.event_gallery.cloudinary.api.delete_resources')
    def test_bulk_delete_uses_cloudinary_batches_of_one_hundred(self, delete_resources):
        public_ids = [f'oef/test/events/photo-{index}' for index in range(120)]
        barrier = Barrier(2)
        lock = Lock()
        active = 0
        peak = 0

        def delete_batch(batch, **_kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                barrier.wait(timeout=2)
                return {'deleted': {public_id: 'deleted' for public_id in batch}}
            finally:
                with lock:
                    active -= 1

        delete_resources.side_effect = delete_batch

        deleted, failed = delete_event_images(public_ids)

        self.assertEqual(deleted, set(public_ids))
        self.assertEqual(failed, {})
        self.assertEqual(peak, 2)
        self.assertEqual(delete_resources.call_count, 2)
        self.assertEqual(len(delete_resources.call_args_list[0].args[0]), 100)
        self.assertEqual(len(delete_resources.call_args_list[1].args[0]), 20)
        for call in delete_resources.call_args_list:
            self.assertEqual(call.kwargs, {
                'resource_type': 'image', 'type': 'upload', 'invalidate': True,
            })

    @patch('mainsite.services.event_gallery.cloudinary.api.delete_resources')
    def test_bulk_delete_preserves_ids_from_a_failed_provider_batch(self, delete_resources):
        public_ids = [f'oef/test/events/photo-{index}' for index in range(120)]

        def delete_batch(batch, **_kwargs):
            if batch[0] == public_ids[100]:
                raise RuntimeError('provider unavailable')
            return {'deleted': {public_id: 'deleted' for public_id in batch}}

        delete_resources.side_effect = delete_batch

        deleted, failed = delete_event_images(public_ids)

        self.assertEqual(deleted, set(public_ids[:100]))
        self.assertEqual(set(failed), set(public_ids[100:]))

    @patch('mainsite.services.event_gallery._normalise_asset')
    @patch('mainsite.services.event_gallery.cloudinary.uploader.upload')
    @patch('blog.media.validate_editorial_image')
    def test_upload_uses_environment_event_tags_and_metadata(self, validate, upload, normalise):
        event = SimpleNamespace(pk=3, gallery_tag='oef-event-123', title='Community day')
        image = Mock(name='image')
        upload.return_value = {'public_id': 'oef/test/events/oef-event-123/photo'}
        normalise.return_value = Mock()

        upload_event_image(
            event, image, alt_text='Volunteers serving meals',
            caption='Community outreach', tags=('Food Relief', 'Volunteers'),
        )

        validate.assert_called_once_with(image, max_bytes=12 * 1024 * 1024)
        kwargs = upload.call_args.kwargs
        self.assertEqual(kwargs['folder'], cloudinary_folder('events', 'oef-event-123'))
        self.assertIn(cloudinary_environment_tag(), kwargs['tags'])
        self.assertIn('oef-event-123', kwargs['tags'])
        self.assertNotIn('publication-approved', kwargs['tags'])
        self.assertEqual(kwargs['context']['alt'], 'Volunteers serving meals')

    @patch('mainsite.services.event_gallery._normalise_asset')
    @patch('mainsite.services.event_gallery.cloudinary.uploader.upload')
    @patch('blog.media.validate_editorial_image')
    def test_upload_generates_accessible_fallback_when_alt_is_blank(self, validate, upload, normalise):
        event = SimpleNamespace(pk=4, gallery_tag='community-day', title='Community Day')
        image = Mock(name='image')
        upload.return_value = {'public_id': 'oef/test/events/community-day/photo'}
        normalise.return_value = Mock()
        upload_event_image(event, image)
        self.assertEqual(upload.call_args.kwargs['context']['alt'], 'Community Day photograph')
        self.assertNotIn('publication-approved', upload.call_args.kwargs['tags'])

    @patch('mainsite.services.event_gallery._normalise_asset')
    @patch('mainsite.services.event_gallery.cloudinary.uploader.explicit')
    @patch('mainsite.services.event_gallery._find_event_asset')
    def test_metadata_update_does_not_manage_database_publication(self, find_asset, explicit, normalise):
        event = SimpleNamespace(pk=5, gallery_tag='community-day', title='Community Day')
        find_asset.return_value = GalleryAsset(
            asset_id='asset-5', public_id='oef/test/events/community-day/photo',
            url='https://example.com/photo.jpg', thumbnail_url='https://example.com/thumb.jpg',
            width=1200, height=800, alt='Community Day photograph', caption='',
            tags=('community-day', 'oef-environment-test'),
        )
        explicit.return_value = {'public_id': 'oef/test/events/community-day/photo'}
        normalise.return_value = Mock()

        update_event_image_metadata(
            event, 'oef/test/events/community-day/photo',
            alt_text='Volunteers preparing meals', caption='Community Day',
            tags=('volunteers',),
        )

        kwargs = explicit.call_args.kwargs
        self.assertNotIn('publication-approved', kwargs['tags'])
        self.assertIn('community-day', kwargs['tags'])
        self.assertEqual(kwargs['context']['alt'], 'Volunteers preparing meals')


@override_settings(
    CLOUDINARY_GALLERY_ENABLED=True,
    CLOUDINARY_GALLERIES=GALLERIES,
)
class PublicGalleryRetirementTests(TestCase):
    def setUp(self):
        self.event = Events.objects.create(
            title='Feed Someone 1.0', event_date=date(2019, 12, 27),
            event_slug='feed-someone-1-0', location='Akure',
            feature_img='event_feature_img/test.jpg', time='11:00',
            content='Community relief.', gallery_tag='feed-someone-1.0',
            gallery_is_public=True,
        )

    def test_standalone_gallery_redirects_permanently_to_impact(self):
        response = self.client.get(
            reverse('mainsite:gallery'), {'event': self.event.event_slug},
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse('mainsite:impact'))

    def test_impact_page_uses_single_column_record_detail_flow(self):
        response = self.client.get(reverse('mainsite:impact'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'View impact details')
        self.assertContains(response, 'oef-impact-card')
        self.assertContains(response, 'oef-impact-list')
        self.assertNotContains(response, 'col-lg-6 col-md-6')
        self.assertNotContains(response, 'class="blog_item_date"')
        self.assertContains(response, 'Community action since 2019')
        self.assertContains(response, 'Practical support that protects dignity and opens pathways forward')
        self.assertContains(response, 'meeting urgent needs with care')
        self.assertNotContains(response, 'grant-ready')
        self.assertNotContains(response, 'marked for verification')
        self.assertNotContains(response, 'evidence-safe reporting')
        self.assertNotContains(response, 'cautious evidence-based reporting')
        self.assertContains(response, 'Review transparency notes')
        self.assertNotContains(response, 'Impact records are being strengthened as OEF prepares')
        self.assertContains(
            response,
            reverse('event-details', kwargs={
                'pk': self.event.pk, 'slug': self.event.event_slug,
            }),
        )
        self.assertNotContains(response, '?event=')


@override_settings(CLOUDINARY_GALLERY_ENABLED=False, CLOUDINARY_GALLERIES=GALLERIES)
class GalleryPrivacyGateTests(TestCase):
    def test_disabled_gallery_does_not_expose_internal_review_state(self):
        event = Events.objects.create(
            title='Feed Someone 2.0', event_date=date(2020, 12, 27),
            event_slug='feed-someone-2-0', location='Akure',
            feature_img='event_feature_img/test.jpg', time='11:00',
            content='Community relief.', gallery_tag='feed-someone-2.0',
            gallery_is_public=True,
        )
        response = self.client.get(
            reverse('mainsite:gallery'),
            {'event': event.event_slug},
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse('mainsite:impact'))
