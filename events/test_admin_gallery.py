from datetime import date, timedelta
from io import BytesIO
from threading import Barrier, Lock
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from PIL import Image

from blog.media import validate_event_images_can_be_made_private
from blog.models import Article, ArticleRevision, MediaAsset
from events.models import (EventGallery, EventGalleryImage, Events,
                           GalleryUploadBatch, GalleryUploadItem)
from mainsite.services.event_gallery import GalleryAsset
from utils.cloudinary_paths import cloudinary_environment_tag


class EventGalleryAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='galleryadmin', email='gallery@example.com', password='test-pass-123',
        )
        self.client.force_login(self.admin)
        self.event = Events.objects.create(
            title='Future event', event_date=date(2026, 9, 1), event_slug='future-event',
            location='Akure', feature_img='event_feature_img/test.jpg', time='10:00',
            content='Event content.',
        )

    def test_legacy_event_gallery_route_redirects_to_compact_table(self):
        response = self.client.get(reverse('admin:events_events_gallery', args=(self.event.pk,)))
        self.assertRedirects(
            response,
            f'{reverse("admin:events_eventgalleryimage_changelist")}?event__id__exact={self.event.pk}',
            fetch_redirect_response=False,
        )

    def test_admin_navigation_exposes_events_and_gallery_manager(self):
        response = self.client.get(reverse('admin:events_events_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add images')
        self.assertContains(
            response,
            reverse('admin:events_eventgalleryimage_upload'),
        )
        menu_entries = settings.BATON['MENU']
        self.assertIn(
            {
                'type': 'model',
                'label': 'Gallery images',
                'name': 'eventgalleryimage',
                'app': 'events',
                'icon': 'fa fa-picture-o',
            },
            menu_entries,
        )

    def test_duplicate_event_gallery_proxy_is_not_registered(self):
        self.assertNotIn(EventGallery, admin.site._registry)
        self.assertIn(EventGalleryImage, admin.site._registry)

    def test_event_deletion_is_protected_while_gallery_images_remain(self):
        image = EventGalleryImage.objects.create(
            event=self.event,
            asset_id='asset-parent-delete-protected',
            public_id='oef/local/events/future/parent-delete-protected',
            secure_url='https://example.com/parent-delete-protected.jpg',
            original_filename='parent-delete-protected.jpg',
            uploaded_by=self.admin,
        )

        with self.assertRaises(ProtectedError):
            self.event.delete()

        self.assertTrue(Events.objects.filter(pk=self.event.pk).exists())
        self.assertTrue(EventGalleryImage.objects.filter(pk=image.pk).exists())

    def test_event_admin_removes_default_bulk_delete_action(self):
        response = self.client.get(reverse('admin:events_events_changelist'))
        events_admin = admin.site._registry[Events]

        self.assertNotIn(
            'delete_selected', events_admin.get_actions(response.wsgi_request),
        )

    def test_event_delete_view_explains_required_gallery_cleanup(self):
        image = EventGalleryImage.objects.create(
            event=self.event,
            asset_id='asset-admin-parent-delete-protected',
            public_id='oef/local/events/future/admin-parent-delete-protected',
            secure_url='https://example.com/admin-parent-delete-protected.jpg',
            original_filename='admin-parent-delete-protected.jpg',
            uploaded_by=self.admin,
        )

        response = self.client.post(
            reverse('admin:events_events_delete', args=(self.event.pk,)),
            {'post': 'yes'},
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse('admin:events_events_change', args=(self.event.pk,)),
        )
        self.assertContains(
            response,
            'This event cannot be deleted while gallery images remain.',
        )
        self.assertTrue(Events.objects.filter(pk=self.event.pk).exists())
        self.assertTrue(EventGalleryImage.objects.filter(pk=image.pk).exists())

    def test_obsolete_per_event_mutation_routes_are_removed(self):
        for name in (
            'admin:events_events_gallery_upload',
            'admin:events_events_gallery_update',
            'admin:events_events_gallery_delete',
        ):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(name, args=(self.event.pk,))

    def test_legacy_frontend_uploader_redirects_to_event_admin(self):
        response = self.client.get(reverse('mainsite:imageuploader'))
        self.assertRedirects(
            response, reverse('admin:events_events_changelist'),
            fetch_redirect_response=False,
        )

    def _image(self, name='photo.jpg'):
        stream = BytesIO()
        Image.new('RGB', (80, 60), '#1f2b7b').save(stream, format='JPEG')
        return SimpleUploadedFile(name, stream.getvalue(), content_type='image/jpeg')

    def _published_event_asset(self, *, slug='published-event-media'):
        Events.objects.filter(pk=self.event.pk).update(gallery_is_public=True)
        self.event.refresh_from_db()
        image = EventGalleryImage.objects.create(
            event=self.event,
            asset_id=f'asset-{slug}',
            public_id=f'oef/local/events/future/{slug}',
            secure_url=f'https://example.com/{slug}.jpg',
            original_filename=f'{slug}.jpg',
            is_public=True,
            uploaded_by=self.admin,
        )
        asset = MediaAsset.objects.create(
            source_event_image=image,
            asset_id=image.asset_id,
            public_id=image.public_id,
            secure_url=image.secure_url,
            original_filename=image.original_filename,
            format='jpg', width=1600, height=900, bytes=0,
            uploaded_by=self.admin,
        )
        article = Article.objects.create(
            article_title='Published event media article',
            article_slug=slug,
            article_content='<p>Published copy.</p>',
            article_author=self.admin,
            is_published=True,
        )
        revision = ArticleRevision.objects.create(
            article=article, iteration=1, title=article.article_title,
            content='<p>Published copy.</p>', feature_image_url=image.secure_url,
            status=ArticleRevision.Status.APPROVED, created_by=self.admin,
            snapshot_locked=False,
        )
        revision.media_assets.add(asset)
        revision.snapshot_locked = True
        revision.save(update_fields=('snapshot_locked',))
        article.published_revision = revision
        article.save(update_fields=('published_revision',))
        return image

    @patch('events.admin.remove_publication_tag')
    def test_bulk_private_action_refuses_live_article_media(self, remove_tag):
        image = self._published_event_asset(slug='bulk-private-live')

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_changelist'),
            {
                'action': 'mark_selected_images_private',
                '_selected_action': [image.pk],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        remove_tag.assert_not_called()
        image.refresh_from_db()
        self.assertTrue(image.is_public)

    def test_bulk_private_validation_uses_one_live_usage_query(self):
        images = EventGalleryImage.objects.bulk_create([
            EventGalleryImage(
                event=self.event,
                asset_id=f'bounded-validation-{index}',
                public_id=f'oef/local/events/future/bounded-validation-{index}',
                secure_url=f'https://example.com/bounded-validation-{index}.jpg',
                original_filename=f'bounded-validation-{index}.jpg',
                uploaded_by=self.admin,
            )
            for index in range(10)
        ])

        with self.assertNumQueries(1):
            validate_event_images_can_be_made_private(images)

    @patch('events.admin.remove_publication_tag')
    @patch('events.admin.add_publication_tag')
    def test_direct_private_edit_refuses_live_article_media(self, add_tag, remove_tag):
        image = self._published_event_asset(slug='direct-private-live')
        image.is_public = False
        image_admin = admin.site._registry[EventGalleryImage]

        with self.assertRaisesMessage(ValidationError, 'published articles'):
            image_admin.save_model(
                None, image, Mock(changed_data=['is_public']), True,
            )

        remove_tag.assert_not_called()
        add_tag.assert_not_called()
        image.refresh_from_db()
        self.assertTrue(image.is_public)

    def test_parent_gallery_cannot_be_hidden_while_live_article_uses_image(self):
        self._published_event_asset(slug='parent-private-live')
        candidate = Events.objects.get(pk=self.event.pk)
        candidate.gallery_is_public = False
        events_admin = admin.site._registry[Events]

        with self.assertRaisesMessage(ValidationError, 'published articles'):
            events_admin.save_model(
                None, candidate, Mock(changed_data=['gallery_is_public']), True,
            )

        self.event.refresh_from_db()
        self.assertTrue(self.event.gallery_is_public)

    def test_parent_gallery_privacy_error_is_rendered_on_change_form(self):
        self._published_event_asset(slug='parent-private-form-error')

        response = self.client.post(
            reverse('admin:events_events_change', args=(self.event.pk,)),
            {
                'title': self.event.title,
                'event_date': self.event.event_date.isoformat(),
                'description': self.event.description or '',
                'location': self.event.location,
                'max_volunteer_needed': '',
                'budget': '',
                'event_slug': self.event.event_slug,
                'time': self.event.time,
                'content': self.event.content,
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Remove or replace them in the published articles, then try again.',
        )
        self.event.refresh_from_db()
        self.assertTrue(self.event.gallery_is_public)

    def test_central_upload_is_separate_from_compact_gallery_table(self):
        upload = self.client.get(reverse('admin:events_eventgalleryimage_upload'))
        table = self.client.get(reverse('admin:events_eventgalleryimage_changelist'))

        self.assertEqual(upload.status_code, 200)
        self.assertContains(upload, 'Drop photographs here')
        self.assertContains(upload, 'staged first')
        self.assertContains(upload, 'Alternative text can also be edited later')
        self.assertContains(upload, 'gallery-batch-upload.js')
        self.assertContains(upload, 'max-height:80vh')
        self.assertContains(upload, 'overflow-y:auto')
        self.assertContains(upload, 'Additional tags')
        self.assertContains(upload, 'Upload images')
        self.assertNotContains(upload, 'Caption')
        self.assertNotContains(upload, 'Cloudinary')
        self.assertEqual(table.status_code, 200)
        self.assertContains(table, 'Add images')
        self.assertNotContains(table, 'Cloudinary images')
        image_admin = admin.site._registry[EventGalleryImage]
        self.assertIn('mark_selected_images_public', image_admin.get_actions(upload.wsgi_request))

    def test_images_are_staged_locally_before_cloudinary_upload(self):
        response = self.client.post(
            reverse('admin:events_eventgalleryimage_stage'),
            {'images': [self._image()]},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 201)
        batch = GalleryUploadBatch.objects.get(pk=response.json()['batch_id'])
        item = batch.items.get()
        self.assertEqual(item.original_filename, 'photo.jpg')
        self.assertTrue(item.staged_file.storage.exists(item.staged_file.name))
        self.client.post(
            reverse('admin:events_eventgalleryimage_cancel_batch'),
            {'batch_id': batch.pk}, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertFalse(GalleryUploadBatch.objects.filter(pk=batch.pk).exists())
        self.assertFalse(item.staged_file.storage.exists(item.staged_file.name))
        self.assertFalse(EventGalleryImage.objects.exists())

    @patch('events.admin.add_publication_tag')
    def test_bulk_action_tags_165_images_once_then_publishes_database_rows(self, add_tag):
        records = EventGalleryImage.objects.bulk_create([
            EventGalleryImage(
                event=self.event, asset_id=f'asset-private-{index}',
                public_id=f'oef/local/events/future/private-{index}',
                secure_url=f'https://example.com/private-{index}.jpg',
                original_filename=f'private-{index}.jpg',
                alt_text='Volunteers serving meals', tags=['volunteers'],
                uploaded_by=self.admin,
            )
            for index in range(165)
        ])

        with self.assertLogs('events.admin', level='INFO') as captured:
            response = self.client.post(
                reverse('admin:events_eventgalleryimage_changelist'),
                {
                    'action': 'mark_selected_images_public',
                    '_selected_action': [record.pk for record in records],
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        add_tag.assert_called_once()
        self.assertEqual(len(add_tag.call_args.args[0]), 165)
        self.event.refresh_from_db()
        self.assertEqual(
            EventGalleryImage.objects.filter(is_public=True).count(), 165,
        )
        self.assertFalse(self.event.gallery_is_public)
        self.assertTrue(any(
            'action=images_marked_public' in entry
            and 'count=165' in entry
            and 'occurred_at=' in entry
            for entry in captured.output
        ))

    @patch('events.admin.remove_publication_tag')
    @patch('events.admin.add_publication_tag', side_effect=RuntimeError('provider unavailable'))
    def test_bulk_public_action_keeps_database_private_when_tag_request_fails(
        self, add_tag, remove_tag,
    ):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-private',
            public_id='oef/local/events/future/private-failed',
            secure_url='https://example.com/private-failed.jpg',
            original_filename='private-failed.jpg', uploaded_by=self.admin,
        )

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_changelist'),
            {
                'action': 'mark_selected_images_public',
                '_selected_action': [record.pk],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        add_tag.assert_called_once_with([record.public_id])
        remove_tag.assert_called_once_with([record.public_id])
        record.refresh_from_db()
        self.event.refresh_from_db()
        self.assertFalse(record.is_public)
        self.assertFalse(self.event.gallery_is_public)

    @patch('events.admin.upload_event_image')
    def test_confirmed_batch_upload_creates_database_index_without_caption(self, upload_image):
        upload_image.return_value = GalleryAsset(
            asset_id='asset-new', public_id='oef/local/events/future/photo-new',
            url='https://example.com/photo-new.jpg', thumbnail_url='https://example.com/thumb-new.jpg',
            width=1200, height=800, alt='Volunteers serving meals', caption='',
            tags=(self.event.gallery_tag, cloudinary_environment_tag(), 'oef-event-gallery', 'volunteers'),
        )
        batch = GalleryUploadBatch.objects.create(created_by=self.admin)
        item = GalleryUploadItem.objects.create(
            batch=batch, staged_file=self._image(), original_filename='photo.jpg',
        )

        with self.assertLogs('events.admin', level='INFO') as captured:
            response = self.client.post(
                reverse('admin:events_eventgalleryimage_commit'),
                {
                    'batch_id': batch.pk, 'event': self.event.pk,
                    'tags': 'volunteers, food-relief',
                    f'alt_text_{item.pk}': 'Volunteers serving meals',
                },
            )

        self.assertEqual(response.status_code, 302)
        record = EventGalleryImage.objects.get(public_id='oef/local/events/future/photo-new')
        self.assertEqual(record.event, self.event)
        self.assertEqual(record.alt_text, 'Volunteers serving meals')
        self.assertEqual(record.tags, ['volunteers'])
        self.assertFalse(record.is_public)
        self.assertFalse(GalleryUploadBatch.objects.filter(pk=batch.pk).exists())
        self.assertEqual(upload_image.call_args.kwargs['caption'], '')
        self.assertNotIn('approved', upload_image.call_args.kwargs)
        self.assertTrue(any(
            'action=images_uploaded' in entry
            and 'count=1' in entry
            and 'occurred_at=' in entry
            for entry in captured.output
        ))

    @patch('events.admin.upload_event_image')
    def test_confirmed_batch_upload_runs_cloudinary_calls_concurrently(self, upload_image):
        barrier = Barrier(2)
        lock = Lock()
        active = 0
        peak = 0

        def upload(_event, staged, **_kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                barrier.wait(timeout=5)
                stem = staged.name.rsplit('.', 1)[0]
                return GalleryAsset(
                    asset_id=f'asset-{stem}', public_id=f'oef/local/events/future/{stem}',
                    url=f'https://example.com/{stem}.jpg',
                    thumbnail_url=f'https://example.com/{stem}-thumb.jpg',
                    width=1200, height=800, alt=f'{stem} photograph', caption='',
                    tags=(self.event.gallery_tag, cloudinary_environment_tag(), 'oef-event-gallery'),
                )
            finally:
                with lock:
                    active -= 1

        upload_image.side_effect = upload
        batch = GalleryUploadBatch.objects.create(created_by=self.admin)
        for name in ('first.jpg', 'second.jpg'):
            GalleryUploadItem.objects.create(
                batch=batch, staged_file=self._image(name), original_filename=name,
            )

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_commit'),
            {'batch_id': batch.pk, 'event': self.event.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(peak, 2)
        self.assertEqual(EventGalleryImage.objects.count(), 2)

    @patch('events.admin.upload_event_image')
    def test_revoked_user_cannot_commit_owned_staged_batch(self, upload_image):
        user = get_user_model().objects.create_user(
            username='revoked-uploader', email='revoked@example.com',
            password='test-pass-123', is_staff=True,
        )
        permissions = Permission.objects.filter(
            content_type__app_label='events',
            codename__in=('view_eventgalleryimage', 'change_eventgalleryimage'),
        )
        user.user_permissions.add(*permissions)
        batch = GalleryUploadBatch.objects.create(created_by=user)
        GalleryUploadItem.objects.create(
            batch=batch, staged_file=self._image(), original_filename='photo.jpg',
        )
        user.user_permissions.clear()
        self.client.force_login(user)

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_commit'),
            {'batch_id': batch.pk, 'event': self.event.pk},
        )

        self.assertEqual(response.status_code, 403)
        upload_image.assert_not_called()
        self.assertTrue(GalleryUploadBatch.objects.filter(pk=batch.pk).exists())
        self.assertFalse(EventGalleryImage.objects.exists())

    @patch('events.admin.upload_event_image')
    def test_expired_batch_is_deleted_without_cloudinary_upload(self, upload_image):
        batch = GalleryUploadBatch.objects.create(created_by=self.admin)
        item = GalleryUploadItem.objects.create(
            batch=batch, staged_file=self._image(), original_filename='photo.jpg',
        )
        staged_name = item.staged_file.name
        storage = item.staged_file.storage
        GalleryUploadBatch.objects.filter(pk=batch.pk).update(
            created_at=timezone.now() - timedelta(hours=25),
        )

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_commit'),
            {'batch_id': batch.pk, 'event': self.event.pk},
        )

        self.assertEqual(response.status_code, 302)
        upload_image.assert_not_called()
        self.assertFalse(GalleryUploadBatch.objects.filter(pk=batch.pk).exists())
        self.assertFalse(storage.exists(staged_name))
        self.assertFalse(EventGalleryImage.objects.exists())

    @patch('events.admin.delete_event_images')
    def test_table_bulk_delete_removes_cloudinary_asset_and_database_row(self, delete_images):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-delete', public_id='oef/local/events/future/delete',
            secure_url='https://example.com/delete.jpg', original_filename='delete.jpg',
            uploaded_by=self.admin,
        )
        delete_images.return_value = ({record.public_id}, {})
        with self.assertLogs('events.admin', level='INFO') as captured:
            response = self.client.post(
                reverse('admin:events_eventgalleryimage_changelist'),
                {'action': 'delete_selected_gallery_images', '_selected_action': [record.pk]},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1 image(s) deleted.')
        self.assertNotContains(response, 'deleted from Cloudinary')
        self.assertNotContains(response, 'gallery table')
        delete_images.assert_called_once_with([record.public_id])
        self.assertFalse(EventGalleryImage.objects.filter(pk=record.pk).exists())
        self.assertTrue(any(
            'action=images_deleted' in entry
            and 'count=1' in entry
            and 'occurred_at=' in entry
            for entry in captured.output
        ))

    @patch('events.admin.delete_event_images')
    def test_table_bulk_delete_logs_staging_error_without_exposing_details(self, delete_images):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-staging-error',
            public_id='oef/local/events/future/staging-error',
            secure_url='https://example.com/staging-error.jpg',
            original_filename='staging-error.jpg', uploaded_by=self.admin,
        )

        with (
            patch(
                'events.admin.event_image_ids_with_editorial_usage',
                side_effect=RuntimeError('sensitive database implementation details'),
            ),
            patch('events.admin.logger.exception') as log_exception,
        ):
            response = self.client.post(
                reverse('admin:events_eventgalleryimage_changelist'),
                {
                    'action': 'delete_selected_gallery_images',
                    '_selected_action': [record.pk],
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The deletion request could not be started')
        self.assertNotContains(response, 'sensitive database implementation details')
        log_exception.assert_called_once()
        delete_images.assert_not_called()
        record.refresh_from_db()
        self.assertEqual(
            record.deletion_status,
            EventGalleryImage.DeletionStatus.ACTIVE,
        )

    @patch('events.admin.delete_event_images')
    def test_table_bulk_delete_skips_editorial_sources_before_provider_call(self, delete_images):
        protected = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-used', public_id='oef/local/events/future/used',
            secure_url='https://example.com/used.jpg', original_filename='used.jpg',
            uploaded_by=self.admin,
        )
        asset = MediaAsset.objects.create(
            source_event_image=protected,
            asset_id=protected.asset_id,
            public_id=protected.public_id,
            secure_url=protected.secure_url,
            original_filename=protected.original_filename,
            format='jpg', width=1600, height=900, bytes=0,
            uploaded_by=self.admin,
        )
        Article.objects.create(
            article_title='Article using event image',
            article_slug='article-using-event-image',
            article_content='<p>Editorial copy.</p>',
            article_author=self.admin,
            feature_media=asset,
        )

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_changelist'),
            {'action': 'delete_selected_gallery_images', '_selected_action': [protected.pk]},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delete_images.assert_not_called()
        self.assertTrue(EventGalleryImage.objects.filter(pk=protected.pk).exists())

    @patch('events.admin.delete_event_images')
    def test_table_bulk_delete_removes_an_unused_editorial_adoption(self, delete_images):
        image = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-unused',
            public_id='oef/local/events/future/unused',
            secure_url='https://example.com/unused.jpg', original_filename='unused.jpg',
            uploaded_by=self.admin,
        )
        asset = MediaAsset.objects.create(
            source_event_image=image,
            asset_id=image.asset_id,
            public_id=image.public_id,
            secure_url=image.secure_url,
            original_filename=image.original_filename,
            format='jpg', width=1600, height=900, bytes=0,
            uploaded_by=self.admin,
        )
        delete_images.return_value = ({image.public_id}, {})

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_changelist'),
            {'action': 'delete_selected_gallery_images', '_selected_action': [image.pk]},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delete_images.assert_called_once_with([image.public_id])
        self.assertFalse(MediaAsset.objects.filter(pk=asset.pk).exists())
        self.assertFalse(EventGalleryImage.objects.filter(pk=image.pk).exists())

    @patch('events.admin.delete_event_images')
    def test_table_bulk_delete_preserves_unconfirmed_database_rows(self, delete_images):
        deleted_record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-deleted', public_id='oef/local/events/future/deleted',
            secure_url='https://example.com/deleted.jpg', original_filename='deleted.jpg',
            uploaded_by=self.admin,
        )
        failed_record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-failed', public_id='oef/local/events/future/failed',
            secure_url='https://example.com/failed.jpg', original_filename='failed.jpg',
            uploaded_by=self.admin,
        )
        delete_images.return_value = (
            {deleted_record.public_id}, {failed_record.public_id: 'provider unavailable'},
        )

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_changelist'),
            {
                'action': 'delete_selected_gallery_images',
                '_selected_action': [deleted_record.pk, failed_record.pk],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventGalleryImage.objects.filter(pk=deleted_record.pk).exists())
        self.assertTrue(EventGalleryImage.objects.filter(pk=failed_record.pk).exists())
        failed_record.refresh_from_db()
        self.assertEqual(
            failed_record.deletion_status,
            EventGalleryImage.DeletionStatus.ACTIVE,
        )
        self.assertNotIn('provider unavailable', failed_record.deletion_error)
        self.assertIn('Check the server logs', failed_record.deletion_error)

    @patch('events.admin.delete_event_images')
    def test_provider_deleted_state_resumes_local_finalisation_without_second_remote_delete(
        self, delete_images,
    ):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-resumable-delete',
            public_id='oef/local/events/future/resumable-delete',
            secure_url='https://example.com/resumable-delete.jpg',
            original_filename='resumable-delete.jpg', uploaded_by=self.admin,
        )
        delete_images.return_value = ({record.public_id}, {})
        action_data = {
            'action': 'delete_selected_gallery_images',
            '_selected_action': [record.pk],
        }

        with patch(
            'django.db.models.query.QuerySet.delete',
            side_effect=RuntimeError('local finalisation unavailable'),
        ):
            first = self.client.post(
                reverse('admin:events_eventgalleryimage_changelist'),
                action_data,
                follow=True,
            )

        self.assertEqual(first.status_code, 200)
        record.refresh_from_db()
        self.assertEqual(
            record.deletion_status,
            EventGalleryImage.DeletionStatus.PROVIDER_DELETED,
        )
        self.assertNotIn('local finalisation unavailable', record.deletion_error)
        self.assertIn('Check the server logs', record.deletion_error)
        delete_images.assert_called_once_with([record.public_id])

        second = self.client.post(
            reverse('admin:events_eventgalleryimage_changelist'),
            action_data,
            follow=True,
        )

        self.assertEqual(second.status_code, 200)
        self.assertEqual(delete_images.call_count, 1)
        self.assertFalse(EventGalleryImage.objects.filter(pk=record.pk).exists())

    @patch('events.admin.delete_event_images')
    def test_recent_pending_deletion_is_not_started_twice(self, delete_images):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-delete-in-progress',
            public_id='oef/local/events/future/delete-in-progress',
            secure_url='https://example.com/delete-in-progress.jpg',
            original_filename='delete-in-progress.jpg', uploaded_by=self.admin,
            deletion_status=EventGalleryImage.DeletionStatus.PENDING,
            deletion_requested_at=timezone.now(),
        )

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_changelist'),
            {
                'action': 'delete_selected_gallery_images',
                '_selected_action': [record.pk],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delete_images.assert_not_called()
        record.refresh_from_db()
        self.assertEqual(
            record.deletion_status,
            EventGalleryImage.DeletionStatus.PENDING,
        )

    @patch('events.admin.delete_event_images')
    def test_bulk_delete_requires_delete_permission(self, delete_images):
        user = get_user_model().objects.create_user(
            username='gallery-editor', email='gallery-editor@example.com',
            password='test-pass-123', is_staff=True,
        )
        permissions = Permission.objects.filter(
            content_type__app_label='events',
            codename__in=('view_eventgalleryimage', 'change_eventgalleryimage'),
        )
        user.user_permissions.add(*permissions)
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-protected',
            public_id='oef/local/events/future/protected',
            secure_url='https://example.com/protected.jpg',
            original_filename='protected.jpg', uploaded_by=self.admin,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('admin:events_eventgalleryimage_changelist'))
        image_admin = admin.site._registry[EventGalleryImage]

        self.assertNotIn(
            'delete_selected_gallery_images',
            image_admin.get_actions(response.wsgi_request),
        )
        with self.assertRaises(PermissionDenied):
            image_admin.delete_selected_gallery_images(
                response.wsgi_request,
                EventGalleryImage.objects.filter(pk=record.pk),
            )
        delete_images.assert_not_called()
        self.assertTrue(EventGalleryImage.objects.filter(pk=record.pk).exists())

    def test_standard_single_record_delete_is_disabled(self):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-no-direct-delete',
            public_id='oef/local/events/future/no-direct-delete',
            secure_url='https://example.com/no-direct-delete.jpg',
            original_filename='no-direct-delete.jpg', uploaded_by=self.admin,
        )

        response = self.client.get(
            reverse('admin:events_eventgalleryimage_delete', args=(record.pk,))
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(EventGalleryImage.objects.filter(pk=record.pk).exists())

    @patch('events.admin.remove_publication_tag')
    def test_direct_unpublish_preserves_explicit_parent_gate(self, remove_tag):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-public',
            public_id='oef/local/events/future/public',
            secure_url='https://example.com/public.jpg',
            original_filename='public.jpg', is_public=True,
            uploaded_by=self.admin,
        )
        Events.objects.filter(pk=self.event.pk).update(gallery_is_public=True)
        record.is_public = False
        image_admin = admin.site._registry[EventGalleryImage]

        image_admin.save_model(None, record, Mock(changed_data=['is_public']), True)

        remove_tag.assert_called_once_with([record.public_id])
        record.refresh_from_db()
        self.event.refresh_from_db()
        self.assertFalse(record.is_public)
        self.assertTrue(self.event.gallery_is_public)

    @patch('events.admin.update_event_image_metadata')
    def test_metadata_edit_does_not_reopen_private_parent_gallery(self, update_metadata):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-private-parent-edit',
            public_id='oef/local/events/future/private-parent-edit',
            secure_url='https://example.com/private-parent-edit.jpg',
            original_filename='private-parent-edit.jpg', is_public=True,
            uploaded_by=self.admin,
        )
        record.alt_text = 'Updated alternative text'
        image_admin = admin.site._registry[EventGalleryImage]

        image_admin.save_model(
            None, record, Mock(changed_data=['alt_text']), True,
        )

        update_metadata.assert_called_once()
        self.event.refresh_from_db()
        self.assertFalse(self.event.gallery_is_public)

    def test_existing_image_event_is_read_only(self):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-owned',
            public_id='oef/local/events/future/owned',
            secure_url='https://example.com/owned.jpg',
            original_filename='owned.jpg', uploaded_by=self.admin,
        )
        image_admin = admin.site._registry[EventGalleryImage]

        readonly = image_admin.get_readonly_fields(None, record)

        self.assertIn('event', readonly)

    @override_settings(OEF_EVENT_MEDIA_MAX_BATCH_FILES=1)
    def test_stage_rejects_batches_over_file_count_limit(self):
        response = self.client.post(
            reverse('admin:events_eventgalleryimage_stage'),
            {'images': [self._image('one.jpg'), self._image('two.jpg')]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('no more than 1 images', response.json()['error'])
        self.assertFalse(GalleryUploadBatch.objects.exists())

    @patch('events.admin.remove_publication_tag')
    @patch('events.admin.add_publication_tag')
    def test_bulk_publication_compensates_after_database_failure(self, add_tag, remove_tag):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-compensated',
            public_id='oef/local/events/future/compensated',
            secure_url='https://example.com/compensated.jpg',
            original_filename='compensated.jpg', uploaded_by=self.admin,
        )
        response = self.client.get(reverse('admin:events_eventgalleryimage_changelist'))
        image_admin = admin.site._registry[EventGalleryImage]

        with patch(
            'django.db.models.query.QuerySet.update',
            side_effect=RuntimeError('database unavailable'),
        ):
            image_admin.mark_selected_images_public(
                response.wsgi_request, EventGalleryImage.objects.filter(pk=record.pk),
            )

        add_tag.assert_called_once_with([record.public_id])
        remove_tag.assert_called_once_with([record.public_id])
        record.refresh_from_db()
        self.assertFalse(record.is_public)

    @patch('events.admin.remove_publication_tag')
    @patch('events.admin.add_publication_tag')
    def test_bulk_publication_compensates_any_row_not_updated(self, add_tag, remove_tag):
        record = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-not-updated',
            public_id='oef/local/events/future/not-updated',
            secure_url='https://example.com/not-updated.jpg',
            original_filename='not-updated.jpg', uploaded_by=self.admin,
        )
        response = self.client.get(reverse('admin:events_eventgalleryimage_changelist'))
        image_admin = admin.site._registry[EventGalleryImage]

        with patch('django.db.models.query.QuerySet.update', return_value=0):
            image_admin.mark_selected_images_public(
                response.wsgi_request,
                EventGalleryImage.objects.filter(pk=record.pk),
            )

        add_tag.assert_called_once_with([record.public_id])
        remove_tag.assert_called_once_with([record.public_id])
        record.refresh_from_db()
        self.assertFalse(record.is_public)

    @patch('events.admin.upload_event_image', side_effect=RuntimeError('provider unavailable'))
    def test_failed_confirmation_cleans_local_staging(self, upload_image):
        batch = GalleryUploadBatch.objects.create(created_by=self.admin)
        item = GalleryUploadItem.objects.create(
            batch=batch, staged_file=self._image('retry.jpg'),
            original_filename='retry.jpg',
        )
        staged_name = item.staged_file.name
        storage = item.staged_file.storage

        response = self.client.post(
            reverse('admin:events_eventgalleryimage_commit'),
            {'batch_id': batch.pk, 'event': self.event.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(GalleryUploadBatch.objects.filter(pk=batch.pk).exists())
        self.assertFalse(storage.exists(staged_name))
        self.assertFalse(EventGalleryImage.objects.exists())

    @patch('events.management.commands.sync_event_gallery_index.get_admin_gallery_page')
    def test_existing_cloudinary_images_can_be_indexed(self, get_page):
        get_page.return_value = {
            'assets': [GalleryAsset(
                asset_id='asset-existing', public_id='oef/test/events/future/existing',
                url='https://example.com/existing.jpg', thumbnail_url='https://example.com/thumb.jpg',
                width=900, height=600, alt='Existing outreach photograph', caption='',
                tags=(
                    self.event.gallery_tag, cloudinary_environment_tag(),
                    'oef-event-gallery', settings.CLOUDINARY_GALLERY_PUBLICATION_TAG,
                    'volunteers',
                ),
            )],
            'next_cursor': None,
        }

        call_command('sync_event_gallery_index', event=self.event.pk, execute=True)

        image = EventGalleryImage.objects.get(public_id='oef/test/events/future/existing')
        self.assertEqual(image.event, self.event)
        self.assertEqual(image.tags, ['volunteers'])
        self.assertTrue(image.is_public)
        self.event.refresh_from_db()
        self.assertFalse(self.event.gallery_is_public)

    @patch('events.management.commands.sync_event_gallery_index.get_admin_gallery_page')
    def test_cloudinary_sync_preserves_existing_database_publication(self, get_page):
        image = EventGalleryImage.objects.create(
            event=self.event, asset_id='asset-existing',
            public_id='oef/test/events/future/existing',
            secure_url='https://example.com/old.jpg', original_filename='existing.jpg',
            alt_text='Existing photograph', tags=['volunteers'], is_public=True,
            uploaded_by=self.admin,
        )
        get_page.return_value = {
            'assets': [GalleryAsset(
                asset_id='asset-existing', public_id=image.public_id,
                url='https://example.com/new.jpg', thumbnail_url='https://example.com/thumb.jpg',
                width=900, height=600, alt='Updated outreach photograph', caption='',
                tags=(self.event.gallery_tag, cloudinary_environment_tag(), 'oef-event-gallery'),
            )],
            'next_cursor': None,
        }

        call_command('sync_event_gallery_index', event=self.event.pk, execute=True)

        image.refresh_from_db()
        self.assertTrue(image.is_public)
        self.assertEqual(image.secure_url, 'https://example.com/new.jpg')

    @patch('events.management.commands.sync_event_gallery_index.get_admin_gallery_page')
    def test_gallery_index_dry_run_does_not_create_rows(self, get_page):
        get_page.return_value = {
            'assets': [GalleryAsset(
                asset_id='asset-dry', public_id='oef/local/events/future/dry',
                url='https://example.com/dry.jpg', thumbnail_url='https://example.com/thumb.jpg',
                width=900, height=600, alt='Dry run photograph', caption='',
                tags=(self.event.gallery_tag, cloudinary_environment_tag()),
            )],
            'next_cursor': None,
        }

        call_command('sync_event_gallery_index', event=self.event.pk)

        self.assertFalse(EventGalleryImage.objects.exists())

    @patch('events.management.commands.sync_event_gallery_index.get_admin_gallery_page')
    def test_gallery_index_skips_other_environment_assets(self, get_page):
        get_page.return_value = {
            'assets': [GalleryAsset(
                asset_id='asset-prod', public_id='oef/production/events/future/photo',
                url='https://example.com/photo.jpg', thumbnail_url='https://example.com/thumb.jpg',
                width=900, height=600, alt='Production photograph', caption='',
                tags=(self.event.gallery_tag, 'oef-environment-production'),
            )],
            'next_cursor': None,
        }

        call_command('sync_event_gallery_index', event=self.event.pk, execute=True)

        self.assertFalse(EventGalleryImage.objects.exists())

    @patch('events.management.commands.sync_event_gallery_index.get_admin_gallery_page')
    def test_gallery_index_can_require_at_least_one_asset(self, get_page):
        get_page.return_value = {'assets': [], 'next_cursor': None}

        with self.assertRaisesMessage(
            CommandError, 'No environment-matched Cloudinary gallery images were found.',
        ):
            call_command(
                'sync_event_gallery_index', event=self.event.pk,
                execute=True, require_assets=True,
            )

        self.assertFalse(EventGalleryImage.objects.exists())
