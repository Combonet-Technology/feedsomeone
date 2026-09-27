from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from taggit.models import Tag

from blog.forms import ArticleForm
from blog.media import (adopt_event_gallery_image,
                        editorial_public_id_from_url,
                        editorial_public_ids_from_urls,
                        managed_media_public_id_from_url)
from blog.models import Article, ArticleRevision, MediaAsset
from blog.workflow import (approve_revision, publish_approved_revision,
                           publish_article_directly, republish_article,
                           request_changes,
                           return_approved_revision_for_changes,
                           submit_article, unpublish_article)
from events.models import EventGalleryImage, Events
from utils.cloudinary_paths import cloudinary_environment, cloudinary_folder


@override_settings(
    CLOUDINARY_STORAGE={'CLOUD_NAME': 'oef'},
    OEF_EDITORIAL_IMAGE_HOSTS=('res.cloudinary.com',),
)
class EditorialMediaURLTests(TestCase):
    def test_extracts_original_and_transformed_editorial_public_ids(self):
        public_id = f'{cloudinary_folder("editorial")}/community/photo-one'
        urls = {
            f'https://res.cloudinary.com/oef/image/upload/v123/{public_id}.jpg',
            f'https://res.cloudinary.com/oef/image/upload/c_crop,w_800/v123/{public_id}.webp',
            'https://example.com/unmanaged/photo.jpg',
        }

        self.assertEqual(editorial_public_ids_from_urls(urls), {public_id})

    def test_rejects_other_accounts_environments_and_query_string_lookalikes(self):
        public_id = f'{cloudinary_folder("editorial")}/community/photo-one'
        current_environment = cloudinary_environment()
        other_environment = (
            'local' if current_environment == 'production' else 'production'
        )
        wrong_environment = public_id.replace(
            f'/{current_environment}/', f'/{other_environment}/', 1,
        )
        urls = {
            f'https://res.cloudinary.com/another-account/image/upload/v1/{public_id}.jpg',
            f'https://res.cloudinary.com/oef/image/upload/v1/{wrong_environment}.jpg',
            f'https://res.cloudinary.com/oef/image/upload/sample.jpg?id={public_id}',
        }

        self.assertEqual(editorial_public_ids_from_urls(urls), set())
        self.assertTrue(all(editorial_public_id_from_url(url) is None for url in urls))

    def test_accepts_encoded_current_environment_path(self):
        public_id = f'{cloudinary_folder("editorial")}/community/photo one'
        encoded_url = (
            'https://res.cloudinary.com/oef/image/upload/c_fill,w_1200/v9/'
            f'{public_id.replace(" ", "%20")}.webp'
        )

        self.assertEqual(editorial_public_id_from_url(encoded_url), public_id)

    def test_managed_media_parser_accepts_current_environment_event_images(self):
        public_id = f'{cloudinary_folder("events")}/feed-someone/photo-one'
        url = f'https://res.cloudinary.com/oef/image/upload/v9/{public_id}.jpg'

        self.assertEqual(managed_media_public_id_from_url(url), public_id)
        self.assertIsNone(editorial_public_id_from_url(url))

    def test_managed_media_parser_rejects_folder_name_inside_unmanaged_public_id(self):
        public_id = f'{cloudinary_folder("events")}/feed-someone/photo-one'
        lookalike = (
            'https://res.cloudinary.com/oef/image/upload/'
            f'unmanaged-prefix/{public_id}.jpg'
        )

        self.assertIsNone(managed_media_public_id_from_url(lookalike))


def grant(user, *codenames):
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames, content_type__app_label='blog'))


def make_user(email, username):
    return get_user_model().objects.create_user(
        email=email,
        username=username,
        first_name=username.title(),
        last_name='Writer',
        is_staff=True,
    )


def make_image(name='editorial.png'):
    stream = BytesIO()
    Image.new('RGB', (24, 16), color='white').save(stream, format='PNG')
    return SimpleUploadedFile(name, stream.getvalue(), content_type='image/png')


def make_media_asset(user, suffix='1'):
    public_id = f'{cloudinary_folder("editorial")}/image-{suffix}'
    return MediaAsset.objects.create(
        asset_id=f'asset-{suffix}',
        public_id=public_id,
        secure_url=f'https://res.cloudinary.com/oef/image/upload/v1/{public_id}.png',
        original_filename=f'image-{suffix}.png',
        format='png',
        width=1200,
        height=800,
        bytes=2048,
        alt_text='Volunteers preparing community support materials',
        caption='OEF volunteers preparing for an outreach.',
        uploaded_by=user,
    )


@override_settings(
    CLOUDINARY_STORAGE={'CLOUD_NAME': 'oef'},
    OEF_EDITORIAL_IMAGE_HOSTS=('res.cloudinary.com',),
)
class EditorialWorkflowTests(TestCase):
    def setUp(self):
        self.writer = make_user('writer@example.com', 'writer')
        self.reviewer = make_user('reviewer@example.com', 'reviewer')
        grant(self.writer, 'add_article', 'change_article', 'view_article', 'submit_article')
        grant(
            self.reviewer,
            'add_article',
            'change_article',
            'view_article',
            'submit_article',
            'review_article',
            'publish_article',
            'change_articlerevision',
            'view_articlerevision',
        )
        self.article = Article.objects.create(
            article_title='A working draft',
            article_excerpt='A useful summary.',
            article_slug='a-working-draft',
            article_content='<p>Draft body.</p>',
            article_author=self.writer,
        )

    def test_writer_submission_creates_an_immutable_review_snapshot(self):
        revision = submit_article(self.article, self.writer)

        self.article.refresh_from_db()
        self.assertEqual(revision.status, ArticleRevision.Status.IN_REVIEW)
        self.assertEqual(revision.iteration, 1)
        self.assertEqual(self.article.pending_revision, revision)
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.IN_REVIEW)
        revision.title = 'Changed after submission'
        with self.assertRaisesMessage(ValidationError, 'immutable'):
            revision.save()

    def test_submitted_revision_relations_cannot_change(self):
        revision = submit_article(self.article, self.writer)
        asset = make_media_asset(self.writer, 'locked-snapshot')

        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'immutable'):
            revision.media_assets.add(asset)
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'immutable'):
            revision.contributors.add(self.reviewer)
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'immutable'):
            revision.tags.add(Tag.objects.create(name='unreviewed'))
        revision.snapshot_locked = False
        with self.assertRaisesMessage(ValidationError, 'unlocked'):
            revision.save(update_fields=('snapshot_locked',))

    def test_writer_cannot_edit_working_copy_while_revision_is_pending(self):
        submit_article(self.article, self.writer)
        self.client.force_login(self.writer)

        response = self.client.get(reverse('article:update-post', args=[self.article.article_slug]))

        self.assertEqual(response.status_code, 403)

    def test_public_authoring_routes_redirect_into_admin(self):
        self.client.force_login(self.writer)

        create_response = self.client.get(reverse('article:create-article'))
        update_response = self.client.get(
            reverse('article:update-post', args=[self.article.article_slug])
        )

        self.assertRedirects(
            create_response,
            reverse('admin:blog_article_add'),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            update_response,
            reverse('admin:blog_article_change', args=[self.article.pk]),
            fetch_redirect_response=False,
        )

    def test_new_articles_receive_unique_slugs(self):
        form = ArticleForm(data={
            'article_title': self.article.article_title,
            'article_excerpt': 'Another summary.',
            'article_content': '<p>Another article.</p>',
            'tags': 'editorial',
        })
        self.assertTrue(form.is_valid(), form.errors)

        duplicate_title = form.save(commit=False)
        duplicate_title.article_author = self.writer
        duplicate_title.save()

        self.assertEqual(duplicate_title.article_slug, 'a-working-draft-2')

    def test_submission_sanitises_html_and_requires_image_alt_text(self):
        asset = make_media_asset(self.writer, 'sanitised')
        self.article.article_content = (
            '<p>Safe copy.</p><script>alert(1)</script>'
            f'<figure><img src="{asset.secure_url}"></figure>'
        )
        self.article.save()
        with self.assertRaisesMessage(ValidationError, 'alternative text'):
            submit_article(self.article, self.writer)

        self.article.article_content = (
            '<p>Safe copy.</p><script>alert(1)</script>'
            f'<figure><img src="{asset.secure_url}" alt="Food parcels ready for distribution"></figure>'
        )
        self.article.save()
        revision = submit_article(self.article, self.writer)
        self.assertNotIn('<script', revision.content)
        self.assertIn('Food parcels ready for distribution', revision.content)

    def test_cancelled_empty_figure_is_removed_before_submission(self):
        asset = make_media_asset(self.writer, 'empty-figure')
        self.article.article_content = (
            f'<p>Safe copy.</p><figure><img src="{asset.secure_url}" alt="{asset.alt_text}"></figure>'
            '<figure class="figure"><img></figure>'
        )
        self.article.save()

        revision = submit_article(self.article, self.writer)

        self.article.refresh_from_db()
        self.assertNotIn('<img></figure>', revision.content)
        self.assertNotIn('<img></figure>', self.article.article_content)
        self.assertIn(asset.secure_url, revision.content)

    def test_managed_feature_image_is_snapshotted_and_approved_with_revision(self):
        asset = make_media_asset(self.writer, 'feature')
        self.article.feature_media = asset
        self.article.save()

        revision = submit_article(self.article, self.writer)

        self.assertEqual(revision.feature_image_url, asset.feature_url)
        self.assertIn(asset, revision.media_assets.all())
        approve_revision(revision, self.reviewer)
        publish_approved_revision(revision, self.reviewer)
        asset.refresh_from_db()
        self.article.refresh_from_db()
        self.assertTrue(asset.approved_for_publication)
        self.assertEqual(self.article.public_feature_image_url, asset.feature_url)

    def test_custom_feature_crop_is_snapshotted_without_changing_original_asset(self):
        asset = make_media_asset(self.writer, 'custom-feature-crop')
        crop = {'x': 0, 'y': 50, 'width': 1200, 'height': 675}
        self.article.feature_media = asset
        self.article.feature_crop = crop
        self.article.save()

        revision = submit_article(self.article, self.writer)

        self.assertEqual(revision.feature_image_url, asset.cropped_url(crop, 'feature'))
        self.assertNotEqual(revision.feature_image_url, asset.feature_url)
        asset.refresh_from_db()
        self.assertEqual(
            asset.secure_url,
            f'https://res.cloudinary.com/oef/image/upload/v1/{asset.public_id}.png',
        )

    def test_legacy_feature_image_must_be_replaced_or_removed_before_review(self):
        self.article.feature_img = 'article_feature_img/legacy-image.jpg'
        self.article.save()

        with self.assertRaisesMessage(ValidationError, 'legacy feature image'):
            submit_article(self.article, self.writer)

    def test_article_form_can_remove_feature_image(self):
        asset = make_media_asset(self.writer, 'remove')
        self.article.feature_media = asset
        self.article.feature_img = 'article_feature_img/legacy-image.jpg'
        self.article.tags.add('community')
        self.article.save()
        form = ArticleForm(
            data={
                'article_title': self.article.article_title,
                'article_excerpt': self.article.article_excerpt,
                'article_content': self.article.article_content,
                'feature_media': '',
                'clear_feature_image': '1',
                'tags': 'community',
            },
            instance=self.article,
        )

        self.assertTrue(form.is_valid(), form.errors)
        article = form.save()
        self.assertIsNone(article.feature_media)
        self.assertFalse(article.feature_img)

    def test_unapproved_external_and_base64_images_are_rejected(self):
        for source in ('https://example.com/image.jpg', 'data:image/png;base64,AA=='):
            self.article.article_content = f'<p>Copy.</p><img src="{source}" alt="Description">'
            self.article.save()
            with self.assertRaisesMessage(ValidationError, 'approved secure OEF media URL'):
                submit_article(self.article, self.writer)

    def test_current_host_image_must_exist_in_managed_media_library(self):
        public_id = f'{cloudinary_folder("editorial")}/unmanaged'
        self.article.article_content = (
            '<p>Copy.</p>'
            '<img src="https://res.cloudinary.com/oef/image/upload/v1/{}.jpg" '
            'alt="Description">'.format(public_id)
        )
        self.article.save()

        with self.assertRaisesMessage(ValidationError, 'managed OEF media library'):
            submit_article(self.article, self.writer)

    def test_managed_inline_image_is_linked_by_exact_public_id(self):
        asset = make_media_asset(self.writer, 'exact-inline')
        self.article.article_content = (
            f'<p>Copy.</p><img src="{asset.secure_url}" alt="{asset.alt_text}">'
        )
        self.article.save()

        revision = submit_article(self.article, self.writer)

        self.assertEqual(list(revision.media_assets.all()), [asset])

    def test_same_managed_image_can_use_multiple_safe_transform_urls(self):
        asset = make_media_asset(self.writer, 'multiple-transforms')
        second_url = (
            'https://res.cloudinary.com/oef/image/upload/c_fill,w_800/v2/'
            f'{asset.public_id}.webp'
        )
        self.article.article_content = (
            f'<img src="{asset.secure_url}" alt="Original placement">'
            f'<img src="{second_url}" alt="Second placement">'
        )
        self.article.save()

        revision = submit_article(self.article, self.writer)

        self.assertEqual(list(revision.media_assets.all()), [asset])

    def test_adopted_event_image_is_valid_for_feature_and_inline_placements(self):
        event = Events.objects.create(
            title='Adopted Media Event', event_slug='adopted-media-event',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.', gallery_is_public=True,
        )
        public_id = f'{cloudinary_folder("events")}/feed-someone/adopted-photo'
        image = EventGalleryImage.objects.create(
            event=event,
            asset_id='event-asset-workflow',
            public_id=public_id,
            secure_url=f'https://res.cloudinary.com/oef/image/upload/v1/{public_id}.jpg',
            original_filename='adopted-photo.jpg',
            width=1600,
            height=900,
            alt_text='Volunteers supporting community members',
            uploaded_by=self.writer,
            is_public=True,
        )
        asset, _ = adopt_event_gallery_image(image, self.writer)
        self.article.feature_media = asset
        self.article.article_content = (
            f'<p>Copy.</p><img src="{asset.secure_url}" alt="{asset.alt_text}">'
        )
        self.article.save()

        revision = submit_article(self.article, self.writer)

        self.assertIn(asset, revision.media_assets.all())
        self.assertEqual(revision.feature_image_url, asset.feature_url)

    def test_event_folder_asset_without_gallery_provenance_is_rejected(self):
        public_id = f'{cloudinary_folder("events")}/unlinked/orphaned-photo'
        asset = MediaAsset.objects.create(
            asset_id='unlinked-event-workflow', public_id=public_id,
            secure_url=f'https://res.cloudinary.com/oef/image/upload/v1/{public_id}.jpg',
            original_filename='orphaned-photo.jpg', format='jpg',
            width=1600, height=900, bytes=0,
            alt_text='Unlinked event photograph', uploaded_by=self.writer,
        )
        self.article.feature_media = asset
        self.article.save()

        with self.assertRaisesMessage(ValidationError, 'valid gallery source'):
            submit_article(self.article, self.writer)

        self.assertFalse(self.article.revisions.exists())

    def test_private_event_source_cannot_be_submitted(self):
        event = Events.objects.create(
            title='Submission Privacy Test', event_slug='submission-privacy-test',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.', gallery_is_public=True,
        )
        public_id = f'{cloudinary_folder("events")}/privacy/submission'
        image = EventGalleryImage.objects.create(
            event=event, asset_id='privacy-submission', public_id=public_id,
            secure_url=f'https://res.cloudinary.com/oef/image/upload/v1/{public_id}.jpg',
            original_filename='submission.jpg', width=1600, height=900,
            is_public=True, uploaded_by=self.writer,
        )
        asset, _ = adopt_event_gallery_image(image, self.writer)
        self.article.feature_media = asset
        self.article.save()
        image.is_public = False
        image.save(update_fields=('is_public',))

        with self.assertRaisesMessage(ValidationError, 'now private'):
            submit_article(self.article, self.writer)

        self.assertFalse(self.article.revisions.exists())

    def test_event_source_made_private_after_submission_cannot_be_approved(self):
        event = Events.objects.create(
            title='Approval Privacy Test', event_slug='approval-privacy-test',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.', gallery_is_public=True,
        )
        public_id = f'{cloudinary_folder("events")}/privacy/approval'
        image = EventGalleryImage.objects.create(
            event=event, asset_id='privacy-approval', public_id=public_id,
            secure_url=f'https://res.cloudinary.com/oef/image/upload/v1/{public_id}.jpg',
            original_filename='approval.jpg', width=1600, height=900,
            is_public=True, uploaded_by=self.writer,
        )
        asset, _ = adopt_event_gallery_image(image, self.writer)
        self.article.feature_media = asset
        self.article.save()
        revision = submit_article(self.article, self.writer)
        image.is_public = False
        image.save(update_fields=('is_public',))

        with self.assertRaisesMessage(ValidationError, 'now private'):
            approve_revision(revision, self.reviewer)

        revision.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(revision.status, ArticleRevision.Status.IN_REVIEW)
        self.assertEqual(self.article.pending_revision, revision)
        self.assertFalse(self.article.is_published)

    def test_parent_gallery_made_private_after_submission_cannot_be_approved(self):
        event = Events.objects.create(
            title='Parent Approval Privacy', event_slug='parent-approval-privacy',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.', gallery_is_public=True,
        )
        public_id = f'{cloudinary_folder("events")}/privacy/parent-approval'
        image = EventGalleryImage.objects.create(
            event=event, asset_id='privacy-parent-approval', public_id=public_id,
            secure_url=f'https://res.cloudinary.com/oef/image/upload/v1/{public_id}.jpg',
            original_filename='parent-approval.jpg', width=1600, height=900,
            is_public=True, uploaded_by=self.writer,
        )
        asset, _ = adopt_event_gallery_image(image, self.writer)
        self.article.feature_media = asset
        self.article.save()
        revision = submit_article(self.article, self.writer)
        event.gallery_is_public = False
        event.save(update_fields=('gallery_is_public',))

        with self.assertRaisesMessage(ValidationError, 'parent gallery is now private'):
            approve_revision(revision, self.reviewer)

        self.article.refresh_from_db()
        self.assertFalse(self.article.is_published)

    def test_writer_cannot_access_article_import_but_superuser_can(self):
        self.client.force_login(self.writer)
        writer_response = self.client.get(reverse('admin:blog_article_import'))
        superuser = get_user_model().objects.create_superuser(
            email='importer@example.com', username='importer', password='test-pass-123',
        )
        self.client.force_login(superuser)
        superuser_response = self.client.get(reverse('admin:blog_article_import'))

        self.assertEqual(writer_response.status_code, 403)
        self.assertEqual(superuser_response.status_code, 200)

    def test_approval_and_publication_are_separate_and_writer_cannot_self_approve(self):
        revision = submit_article(self.article, self.writer)
        with self.assertRaises(PermissionDenied):
            approve_revision(revision, self.writer)

        approve_revision(revision, self.reviewer)
        self.article.refresh_from_db()
        revision.refresh_from_db()
        self.assertFalse(self.article.is_published)
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.APPROVED)
        publish_approved_revision(revision, self.reviewer)
        self.article.refresh_from_db()
        revision.refresh_from_db()
        self.assertTrue(self.article.is_published)
        self.assertEqual(self.article.published_revision, revision)
        self.assertEqual(revision.status, ArticleRevision.Status.PUBLISHED)

    def test_reviewer_and_publisher_presets_are_independent(self):
        publisher = make_user('publisher-role@example.com', 'publisher-role')
        grant(publisher, 'view_article', 'view_articlerevision', 'publish_article')
        revision = submit_article(self.article, self.writer)
        with self.assertRaises(PermissionDenied):
            publish_approved_revision(revision, self.writer)
        with self.assertRaises(PermissionDenied):
            approve_revision(revision, publisher)
        approve_revision(revision, self.reviewer)
        self.assertFalse(Article.objects.get(pk=self.article.pk).is_published)
        published = publish_approved_revision(revision, publisher)
        self.assertTrue(published.is_published)
        self.assertEqual(published.publication_events.last().actor, publisher)

    def test_reviewer_who_is_author_cannot_approve_even_when_another_user_submits(self):
        grant(self.writer, 'review_article')
        self.article.article_author = self.reviewer
        self.article.save()
        revision = submit_article(self.article, self.writer)
        with self.assertRaisesMessage(ValidationError, 'contributor cannot review'):
            approve_revision(revision, self.reviewer)

    def test_editor_who_changes_draft_is_recorded_as_contributor(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('admin:blog_article_change', args=[self.article.pk]),
            {
                'article_title': self.article.article_title,
                'article_excerpt': self.article.article_excerpt,
                'article_content': '<p>Editor changed this body.</p>',
                'tags': 'editorial',
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.article.draft_contributors.filter(pk=self.reviewer.pk).exists())
        revision = submit_article(self.article, self.writer)
        with self.assertRaisesMessage(ValidationError, 'contributor cannot review'):
            approve_revision(revision, self.reviewer)

    def test_approved_metadata_change_blocks_publication_and_can_be_resubmitted(self):
        revision = submit_article(self.article, self.writer)
        approve_revision(revision, self.reviewer)
        self.article.category.create(title='New category')
        with self.assertRaisesMessage(ValidationError, 'working draft changed'):
            publish_approved_revision(revision, self.reviewer)
        replacement = submit_article(self.article, self.writer)
        self.article.refresh_from_db()
        self.assertEqual(replacement.iteration, 2)
        self.assertEqual(self.article.pending_revision_id, replacement.pk)

    def test_draft_taxonomy_changes_do_not_change_published_discovery(self):
        from blog.models import Categories

        original_category = Categories.objects.create(title='Briefings')
        next_category = Categories.objects.create(title='Articles')
        self.article.category.add(original_category)
        self.article.tags.add('community')
        revision = submit_article(self.article, self.writer)
        approve_revision(revision, self.reviewer)
        publish_approved_revision(revision, self.reviewer)
        self.article.category.set([next_category])
        self.article.tags.set(['internal-draft'])
        self.article.refresh_from_db()
        self.assertEqual(list(self.article.public_categories), [original_category])
        self.assertEqual([tag.name for tag in self.article.public_tags], ['community'])
        self.assertIn(
            self.article.public_title,
            self.client.get(reverse('article:articles-by-category', args=['Briefings'])).content.decode(),
        )
        self.assertNotIn(
            self.article.public_title,
            self.client.get(reverse('article:articles-by-category', args=['Articles'])).content.decode(),
        )

    def test_publisher_can_return_approved_revision_for_changes(self):
        publisher = make_user('returner@example.com', 'returner')
        grant(publisher, 'publish_article')
        revision = submit_article(self.article, self.writer)
        approve_revision(revision, self.reviewer)
        with self.assertRaisesMessage(ValidationError, 'Review notes are required'):
            return_approved_revision_for_changes(revision, publisher, '')
        returned = return_approved_revision_for_changes(
            revision, publisher, 'The source needs verification.',
        )
        self.assertEqual(returned.workflow_status, Article.WorkflowStatus.CHANGES_REQUESTED)
        self.assertIsNone(returned.pending_revision)
        self.assertFalse(returned.is_published)

    def test_unpublish_hides_direct_url_and_sitemap_then_republish_restores_snapshot(self):
        revision = submit_article(self.article, self.writer)
        approve_revision(revision, self.reviewer)
        publish_approved_revision(revision, self.reviewer)
        self.article.refresh_from_db()
        url = self.article.get_absolute_url()
        self.assertEqual(self.client.get(url).status_code, 200)
        unpublish_article(self.article, self.reviewer)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotIn(url, self.client.get('/sitemap.xml').content.decode())
        republish_article(self.article, self.reviewer)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            list(self.article.publication_events.values_list('action', flat=True)),
            ['republish', 'unpublish', 'publish'],
        )

    def test_legacy_unverified_publication_cannot_be_republished(self):
        revision = submit_article(self.article, self.writer)
        approve_revision(revision, self.reviewer)
        publish_approved_revision(revision, self.reviewer)
        ArticleRevision.objects.filter(pk=revision.pk).update(legacy_metadata_unverified=True)
        unpublish_article(self.article, self.reviewer)

        with self.assertRaisesMessage(ValidationError, 'legacy publication'):
            republish_article(self.article, self.reviewer)

    def test_legacy_published_revision_uses_existing_detail_and_author_routes(self):
        revision = submit_article(self.article, self.writer)
        approve_revision(revision, self.reviewer)
        publish_approved_revision(revision, self.reviewer)
        ArticleRevision.objects.filter(pk=revision.pk).update(
            slug='', authored_by=None, legacy_metadata_unverified=True,
        )
        self.article.refresh_from_db()
        outsider = make_user('reader@example.com', 'reader')
        self.client.force_login(outsider)

        self.assertEqual(self.client.get(self.article.get_absolute_url()).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('article:post_share', args=[self.article.article_slug])).status_code,
            200,
        )
        self.assertContains(
            self.client.get(reverse('article:article-by-user', args=[self.writer.username])),
            self.article.public_title,
        )

    def test_editing_after_publication_does_not_replace_live_copy(self):
        first_revision = submit_article(self.article, self.writer)
        approve_revision(first_revision, self.reviewer)
        publish_approved_revision(first_revision, self.reviewer)

        self.article.refresh_from_db()
        self.article.article_title = 'Unreviewed replacement title'
        self.article.article_content = '<p>Unreviewed replacement body.</p>'
        self.article.save()
        self.article.refresh_from_db()

        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.DRAFT)
        self.assertEqual(self.article.public_title, 'A working draft')
        self.assertEqual(self.article.public_content, '<p>Draft body.</p>')

        response = self.client.get(self.article.get_absolute_url())
        self.assertContains(response, 'A working draft')
        self.assertNotContains(response, 'Unreviewed replacement title')
        self.assertNotContains(response, 'Unreviewed replacement body')

    def test_unchanged_admin_save_keeps_published_state_and_revision_count(self):
        self.article.tags.add('community')
        revision = submit_article(self.article, self.writer)
        approve_revision(revision, self.reviewer)
        publish_approved_revision(revision, self.reviewer)
        self.article.refresh_from_db()
        original_revision_count = self.article.revisions.count()
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('admin:blog_article_change', args=[self.article.pk]),
            {
                'article_title': self.article.article_title,
                'article_excerpt': self.article.article_excerpt,
                'article_content': self.article.article_content,
                'tags': 'community',
                '_save': 'Save',
            },
        )

        self.assertFalse(
            response.context['adminform'].form.errors if response.status_code == 200 else {},
            response.context['adminform'].form.errors if response.status_code == 200 else '',
        )
        self.assertEqual(response.status_code, 302)
        self.article.refresh_from_db()
        self.assertEqual(self.article.revisions.count(), original_revision_count)
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.PUBLISHED)
        self.assertTrue(self.article.is_published)
        self.assertEqual(self.article.published_revision, revision)

    def test_saving_revision_notes_alone_does_not_create_or_transition_revision(self):
        revision = submit_article(self.article, self.writer)
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('admin:blog_articlerevision_change', args=[revision.pk]),
            {
                'review_notes': 'A private note that has not been submitted as a decision.',
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.article.refresh_from_db()
        revision.refresh_from_db()
        self.assertEqual(ArticleRevision.objects.filter(article=self.article).count(), 1)
        self.assertEqual(revision.status, ArticleRevision.Status.IN_REVIEW)
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.IN_REVIEW)
        self.assertEqual(self.article.pending_revision, revision)

    def test_admin_submit_button_creates_one_review_snapshot(self):
        self.client.force_login(self.writer)

        response = self.client.post(
            reverse('admin:blog_article_add'),
            {
                'article_title': 'A new admin draft',
                'article_excerpt': 'A summary written in admin.',
                'article_content': '<p>The complete article body.</p>',
                'tags': 'community, relief',
                '_submit_for_review': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        article = Article.objects.get(article_title='A new admin draft')
        self.assertEqual(article.workflow_status, Article.WorkflowStatus.IN_REVIEW)
        self.assertEqual(article.revisions.count(), 1)
        self.assertEqual(article.pending_revision.iteration, 1)
        self.assertFalse(article.is_published)

    def test_superuser_can_publish_directly_with_an_approved_audit_revision(self):
        superuser = get_user_model().objects.create_superuser(
            email='publisher@example.com',
            username='publisher',
            password='test-pass-123',
        )
        self.article.article_author = superuser
        self.article.save()

        published = publish_article_directly(self.article, superuser)

        revision = published.published_revision
        self.assertTrue(published.is_published)
        self.assertEqual(published.workflow_status, Article.WorkflowStatus.PUBLISHED)
        self.assertIsNone(published.pending_revision)
        self.assertEqual(revision.status, ArticleRevision.Status.PUBLISHED)
        self.assertEqual(revision.created_by, superuser)
        self.assertIsNone(revision.reviewed_by)
        self.assertTrue(revision.direct_bypass)
        self.assertEqual(published.publication_events.first().action, 'direct_publish')

    def test_non_superuser_cannot_publish_directly(self):
        with self.assertRaises(PermissionDenied):
            publish_article_directly(self.article, self.reviewer)

    def test_explicit_override_needs_neither_submit_nor_normal_publish_permission(self):
        trusted = make_user('trusted@example.com', 'trusted')
        grant(trusted, 'publish_without_review')
        published = publish_article_directly(self.article, trusted)
        revision = published.published_revision
        self.assertTrue(published.is_published)
        self.assertTrue(revision.direct_bypass)
        self.assertIsNone(revision.reviewed_by)
        self.assertIsNone(revision.reviewed_at)
        self.assertEqual(revision.published_by, trusted)
        self.assertEqual(published.publication_events.get().actor, trusted)
        self.assertEqual(published.publication_events.get().action, 'direct_publish')

    def test_pending_override_reuses_iteration_and_does_not_allow_self_approval(self):
        grant(self.writer, 'publish_without_review', 'review_article')
        revision = submit_article(self.article, self.writer)
        with self.assertRaisesMessage(ValidationError, 'contributor'):
            approve_revision(revision, self.writer)
        published = publish_article_directly(self.article, self.writer, revision=revision)
        self.assertEqual(published.published_revision_id, revision.pk)
        self.assertEqual(published.revisions.count(), 1)
        self.assertIsNone(published.published_revision.reviewed_at)
        with self.assertRaises(ValidationError):
            publish_article_directly(published, self.writer)
        self.assertEqual(published.publication_events.count(), 1)

    def test_override_denies_inactive_and_nonstaff_accounts(self):
        for field in ('is_active', 'is_staff'):
            with self.subTest(field=field):
                trusted = make_user(f'{field}@example.com', field)
                grant(trusted, 'publish_without_review')
                setattr(trusted, field, False)
                trusted.save(update_fields=(field,))
                with self.assertRaises(PermissionDenied):
                    publish_article_directly(self.article, trusted)
        self.assertFalse(self.article.revisions.exists())

    def test_override_rejects_stale_revision_without_publishing_draft_changes(self):
        grant(self.writer, 'publish_without_review')
        revision = submit_article(self.article, self.writer)
        self.article.refresh_from_db()
        self.article.article_content = '<p>Changed after review submission.</p>'
        self.article.save()
        with self.assertRaises(ValidationError):
            publish_article_directly(self.article, self.writer, revision=revision)
        revision.refresh_from_db()
        self.assertFalse(revision.direct_bypass)
        self.assertFalse(self.article.publication_events.exists())

    def test_override_still_validates_content_and_media(self):
        grant(self.writer, 'publish_without_review')
        self.article.article_content = '<p><img src="https://unmanaged.example/image.jpg"></p>'
        self.article.save()
        with self.assertRaises(ValidationError):
            publish_article_directly(self.article, self.writer)
        self.assertFalse(self.article.revisions.exists())

    def test_override_is_not_in_delegable_presets(self):
        from django.contrib.auth.models import Group

        from user.access import DELEGABLE_GROUPS

        for name in ('OEF Writers', 'OEF Reviewers', 'OEF Publishers'):
            Group.objects.get_or_create(name=name)
        self.assertFalse(Group.objects.filter(
            name__in=DELEGABLE_GROUPS,
            permissions__codename='publish_without_review',
            permissions__content_type__app_label='blog',
        ).exists())

    def test_author_with_override_can_publish_pending_revision_through_admin(self):
        grant(self.writer, 'publish_without_review', 'view_articlerevision')
        revision = submit_article(self.article, self.writer)
        self.client.force_login(self.writer)
        article_url = reverse('admin:blog_article_change', args=[self.article.pk])
        revision_url = reverse('admin:blog_articlerevision_change', args=[revision.pk])
        self.assertContains(self.client.get(article_url), 'Publish without review')
        self.assertContains(self.client.get(revision_url), 'Publish without review')
        response = self.client.post(revision_url, {'_publish_without_review': '1'})
        self.assertEqual(response.status_code, 302)
        self.article.refresh_from_db()
        self.assertTrue(self.article.is_published)
        self.assertEqual(self.article.published_revision_id, revision.pk)

    def test_reviewer_cannot_forge_pending_publication_override(self):
        revision = submit_article(self.article, self.writer)
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('admin:blog_articlerevision_change', args=[revision.pk]),
            {'_publish_without_review': '1'},
        )
        self.assertEqual(response.status_code, 302)
        self.article.refresh_from_db()
        self.assertFalse(self.article.is_published)
        self.assertFalse(self.article.publication_events.exists())

    def test_superuser_can_bypass_own_pending_review_from_article_form(self):
        owner = get_user_model().objects.create_superuser(
            email='owner-pending@example.com', username='owner-pending', password='test-pass',
        )
        self.article.article_author = owner
        self.article.save()
        self.article.tags.add('community')
        revision = submit_article(self.article, owner)
        with self.assertRaisesMessage(ValidationError, 'contributor'):
            approve_revision(revision, owner)
        self.client.force_login(owner)
        url = reverse('admin:blog_article_change', args=[self.article.pk])
        self.assertContains(self.client.get(url), 'Publish without review')
        response = self.client.post(url, {
            'article_title': self.article.article_title,
            'article_excerpt': self.article.article_excerpt,
            'article_content': self.article.article_content,
            'article_author': owner.pk, 'tags': 'community', '_publish_now': '1',
        })
        self.assertEqual(
            response.status_code, 302,
            response.context['adminform'].form.errors if response.status_code == 200 else '',
        )
        self.article.refresh_from_db()
        self.assertTrue(self.article.is_published)
        self.assertEqual(self.article.published_revision_id, revision.pk)
        self.assertIsNone(self.article.published_revision.reviewed_at)

    def test_override_is_rechecked_after_revocation(self):
        grant(self.writer, 'publish_without_review')
        revision = submit_article(self.article, self.writer)
        self.writer.user_permissions.remove(Permission.objects.get(
            codename='publish_without_review', content_type__app_label='blog',
        ))
        actor = get_user_model().objects.get(pk=self.writer.pk)
        with self.assertRaises(PermissionDenied):
            publish_article_directly(self.article, actor, revision=revision)
        self.assertFalse(self.article.publication_events.exists())

    def test_override_preserves_an_already_approved_revision(self):
        grant(self.writer, 'publish_without_review')
        revision = submit_article(self.article, self.writer)
        approve_revision(revision, self.reviewer)
        with self.assertRaises(ValidationError):
            publish_article_directly(self.article, self.writer, revision=revision)
        revision.refresh_from_db()
        self.assertEqual(revision.status, ArticleRevision.Status.APPROVED)
        self.assertEqual(revision.reviewed_by, self.reviewer)
        self.assertFalse(revision.direct_bypass)
        self.assertEqual(self.article.revisions.count(), 1)
        self.assertFalse(self.article.publication_events.exists())

    def test_superuser_article_form_exposes_publish_now(self):
        superuser = get_user_model().objects.create_superuser(
            email='publisher-ui@example.com',
            username='publisher-ui',
            password='test-pass-123',
        )
        self.client.force_login(superuser)

        response = self.client.get(reverse('admin:blog_article_add'))

        self.assertContains(response, 'Publish without review')
        self.assertContains(response, 'Save and submit for review')
        self.assertContains(response, 'Add Image')
        self.assertNotContains(response, 'Legacy image — replace or remove before review')

    def test_writer_cannot_trigger_publish_now_with_a_crafted_post(self):
        self.client.force_login(self.writer)

        response = self.client.post(
            reverse('admin:blog_article_add'),
            {
                'article_title': 'Writer attempted direct publication',
                'article_excerpt': 'A saved but unpublished draft.',
                'article_content': '<p>The complete article body.</p>',
                'tags': 'community',
                '_publish_now': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        article = Article.objects.get(article_title='Writer attempted direct publication')
        self.assertFalse(article.is_published)
        self.assertEqual(article.workflow_status, Article.WorkflowStatus.DRAFT)
        self.assertEqual(article.revisions.count(), 0)

    def test_admin_review_buttons_apply_explicit_decisions_only(self):
        revision = submit_article(self.article, self.writer)
        self.client.force_login(self.reviewer)

        request_response = self.client.post(
            reverse('admin:blog_articlerevision_change', args=[revision.pk]),
            {
                'review_notes': 'Please clarify the evidence in paragraph two.',
                '_request_changes': '1',
            },
        )

        self.assertEqual(request_response.status_code, 302)
        self.article.refresh_from_db()
        revision.refresh_from_db()
        self.assertEqual(revision.status, ArticleRevision.Status.CHANGES_REQUESTED)
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.CHANGES_REQUESTED)

        replacement = submit_article(self.article, self.writer)
        approve_response = self.client.post(
            reverse('admin:blog_articlerevision_change', args=[replacement.pk]),
            {'review_notes': '', '_approve_revision': '1'},
        )

        self.assertEqual(approve_response.status_code, 302)
        self.article.refresh_from_db()
        replacement.refresh_from_db()
        self.assertEqual(replacement.status, ArticleRevision.Status.APPROVED)
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.APPROVED)
        self.assertFalse(self.article.is_published)
        publish_response = self.client.post(
            reverse('admin:blog_articlerevision_change', args=[replacement.pk]),
            {'_publish_revision': '1'},
        )
        self.assertEqual(publish_response.status_code, 302)
        self.article.refresh_from_db()
        self.assertTrue(self.article.is_published)

    def test_published_article_full_revision_cycle_keeps_old_copy_live_until_approval(self):
        first = submit_article(self.article, self.writer)
        approve_revision(first, self.reviewer)
        publish_approved_revision(first, self.reviewer)
        self.article.refresh_from_db()
        original_url = self.article.get_absolute_url()

        self.article.article_title = 'Reviewed replacement title'
        self.article.article_content = '<p>Reviewed replacement body.</p>'
        self.article.save()
        second = submit_article(self.article, self.writer)

        self.article.refresh_from_db()
        self.assertTrue(self.article.is_published)
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.IN_REVIEW)
        self.assertEqual(self.article.public_title, 'A working draft')

        request_changes(second, self.reviewer, 'Add the source for the main claim.')
        third = submit_article(self.article, self.writer)
        approve_revision(third, self.reviewer)
        publish_approved_revision(third, self.reviewer)

        self.article.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, ArticleRevision.Status.SUPERSEDED)
        self.assertEqual(second.status, ArticleRevision.Status.CHANGES_REQUESTED)
        self.assertEqual(self.article.published_revision, third)
        self.assertEqual(self.article.public_title, 'Reviewed replacement title')
        self.assertEqual(self.article.public_content, '<p>Reviewed replacement body.</p>')
        self.assertEqual(self.article.get_absolute_url(), original_url)

    def test_requesting_changes_requires_notes_and_returns_article_to_writer(self):
        revision = submit_article(self.article, self.writer)
        with self.assertRaisesMessage(ValidationError, 'Review notes are required'):
            request_changes(revision, self.reviewer, '')

        request_changes(revision, self.reviewer, 'Clarify the source for the second paragraph.')
        self.article.refresh_from_db()
        revision.refresh_from_db()
        self.assertIsNone(self.article.pending_revision)
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.CHANGES_REQUESTED)
        self.assertEqual(revision.status, ArticleRevision.Status.CHANGES_REQUESTED)

    def test_writer_sees_current_and_historical_review_notes_on_article_form(self):
        first = submit_article(self.article, self.writer)
        request_changes(first, self.reviewer, 'Add a source and replace the second image.')
        second = submit_article(self.article, self.writer)
        request_changes(second, self.reviewer, 'The source is clearer; shorten the final paragraph.')
        self.client.force_login(self.writer)

        response = self.client.get(reverse('admin:blog_article_change', args=[self.article.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add a source and replace the second image.')
        self.assertContains(response, 'The source is clearer; shorten the final paragraph.')
        self.assertContains(response, 'Revision 1')
        self.assertContains(response, 'Revision 2')
        self.assertContains(response, 'Add Image')
        self.assertContains(response, '/bcx/blog/mediaasset/upload/')
        self.assertContains(response, '/bcx/blog/mediaasset/library/')
        self.assertContains(response, '/bcx/blog/mediaasset/event-library/')
        self.assertNotContains(response, 'Replace Image')
        self.assertNotContains(response, 'data-feature-action="upload"')
        self.assertContains(response, 'Remove')


@override_settings(
    CLOUDINARY_STORAGE={'CLOUD_NAME': 'oef'},
    OEF_EDITORIAL_IMAGE_HOSTS=('res.cloudinary.com',),
    OEF_EDITORIAL_MEDIA_MAX_BYTES=1024 * 1024,
)
class EditorialMediaUploadTests(TestCase):
    def setUp(self):
        self.writer = make_user('media-writer@example.com', 'mediawriter')
        grant(self.writer, 'add_mediaasset', 'view_mediaasset')
        self.client.force_login(self.writer)
        self.url = reverse('admin:blog_mediaasset_upload')
        self.library_url = reverse('admin:blog_mediaasset_library')
        self.event_library_url = reverse('admin:blog_mediaasset_event_library')

    def test_writer_can_load_media_library_as_json(self):
        asset = make_media_asset(self.writer, 'library')

        response = self.client.get(self.library_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['assets'][0]['id'], asset.pk)
        self.assertEqual(response.json()['assets'][0]['url'], asset.transformed_url('inline'))
        self.assertEqual(response.json()['assets'][0]['alt_text'], asset.alt_text)
        self.assertNotIn('variants', response.json()['assets'][0])
        self.assertEqual(
            response.json()['assets'][0]['crop_url'],
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
        )
        self.assertTrue(response.json()['assets'][0]['can_edit'])

    @patch('blog.admin.cloudinary_url')
    def test_writer_can_load_and_adopt_event_image_without_cloudinary_upload(self, cloudinary_url):
        cloudinary_url.return_value = ('https://res.cloudinary.com/oef/image/upload/thumb.jpg', {})
        event = Events.objects.create(
            title='Feed Someone Test', event_slug='feed-someone-test',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.', gallery_is_public=True,
        )
        public_id = f'{cloudinary_folder("events")}/feed-someone/photo-one'
        image = EventGalleryImage.objects.create(
            event=event,
            asset_id='event-asset-1',
            public_id=public_id,
            secure_url=f'https://res.cloudinary.com/oef/image/upload/v1/{public_id}.jpg',
            original_filename='photo-one.jpg',
            width=1600,
            height=900,
            alt_text='Volunteers sharing relief materials',
            is_public=True,
            uploaded_by=self.writer,
        )

        library_response = self.client.get(self.event_library_url)

        self.assertEqual(library_response.status_code, 200)
        event_asset = library_response.json()['assets'][0]
        self.assertEqual(event_asset['event_title'], event.title)
        self.assertEqual(event_asset['url'], cloudinary_url.return_value[0])
        self.assertEqual(event_asset['original_url'], image.secure_url)
        self.assertNotEqual(event_asset['url'], event_asset['original_url'])
        cloudinary_url.assert_called_once_with(
            image.public_id,
            secure=True,
            type='upload',
            width=360,
            height=240,
            crop='fill',
            gravity='auto',
            fetch_format='auto',
            quality='auto',
            dpr='auto',
        )
        self.assertEqual(
            event_asset['adopt_url'],
            reverse('admin:blog_mediaasset_adopt_event', args=(image.pk,)),
        )

        with patch('blog.media.cloudinary.uploader.upload') as upload:
            adopt_response = self.client.post(event_asset['adopt_url'])

        self.assertEqual(adopt_response.status_code, 201)
        upload.assert_not_called()
        adopted = MediaAsset.objects.get(public_id=public_id)
        self.assertEqual(adopted.secure_url, image.secure_url)
        self.assertEqual(adopted.asset_id, image.asset_id)
        self.assertEqual(adopted.source_event_image, image)
        self.assertTrue(adopted.approved_for_publication)
        self.assertEqual(adopt_response.json()['id'], adopted.pk)
        self.assertEqual(
            adopt_response.json()['crop_url'],
            reverse('admin:blog_mediaasset_crop', args=(adopted.pk,)),
        )

        second_response = self.client.post(event_asset['adopt_url'])
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(MediaAsset.objects.filter(public_id=public_id).count(), 1)

    def test_private_event_image_is_hidden_and_cannot_be_adopted(self):
        event = Events.objects.create(
            title='Private Gallery', event_slug='private-gallery',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.',
        )
        private_image = EventGalleryImage.objects.create(
            event=event,
            asset_id='private-event-asset',
            public_id=f'{cloudinary_folder("events")}/private/photo',
            secure_url='https://res.cloudinary.com/oef/image/upload/private.jpg',
            original_filename='private.jpg',
            is_public=False,
            uploaded_by=self.writer,
        )

        library_response = self.client.get(self.event_library_url)
        adopt_response = self.client.post(
            reverse('admin:blog_mediaasset_adopt_event', args=(private_image.pk,))
        )

        self.assertEqual(library_response.status_code, 200)
        self.assertEqual(library_response.json()['assets'], [])
        self.assertEqual(adopt_response.status_code, 404)
        self.assertFalse(MediaAsset.objects.filter(public_id=private_image.public_id).exists())

    def test_image_from_private_parent_gallery_is_hidden_and_cannot_be_adopted(self):
        event = Events.objects.create(
            title='Private Parent Gallery', event_slug='private-parent-gallery',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.', gallery_is_public=False,
        )
        image = EventGalleryImage.objects.create(
            event=event,
            asset_id='private-parent-asset',
            public_id=f'{cloudinary_folder("events")}/private-parent/photo',
            secure_url='https://res.cloudinary.com/oef/image/upload/private-parent.jpg',
            original_filename='private-parent.jpg',
            is_public=True,
            uploaded_by=self.writer,
        )

        library_response = self.client.get(self.event_library_url)
        adopt_response = self.client.post(
            reverse('admin:blog_mediaasset_adopt_event', args=(image.pk,))
        )

        self.assertEqual(library_response.json()['assets'], [])
        self.assertEqual(adopt_response.status_code, 404)
        with self.assertRaisesMessage(ValidationError, 'not available'):
            adopt_event_gallery_image(image, self.writer)

    def test_adopted_event_image_is_hidden_if_its_source_becomes_private(self):
        event = Events.objects.create(
            title='Changing Gallery', event_slug='changing-gallery',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.', gallery_is_public=True,
        )
        public_id = f'{cloudinary_folder("events")}/changing/photo'
        image = EventGalleryImage.objects.create(
            event=event,
            asset_id='changing-event-asset',
            public_id=public_id,
            secure_url=f'https://res.cloudinary.com/oef/image/upload/v1/{public_id}.jpg',
            original_filename='changing.jpg', width=1600, height=900,
            is_public=True, uploaded_by=self.writer,
        )
        asset, _ = adopt_event_gallery_image(image, self.writer)
        image.is_public = False
        image.save(update_fields=('is_public',))

        library_response = self.client.get(self.library_url)
        changelist_response = self.client.get(
            reverse('admin:blog_mediaasset_changelist')
        )
        crop_response = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {'usage': 'inline', 'crop_mode': 'fixed'},
        )

        self.assertEqual(library_response.status_code, 200)
        self.assertEqual(library_response.json()['assets'], [])
        self.assertEqual(changelist_response.status_code, 200)
        self.assertNotContains(changelist_response, asset.original_filename)
        self.assertEqual(crop_response.status_code, 404)

    def test_deletion_pending_event_image_is_hidden_and_cannot_be_submitted(self):
        event = Events.objects.create(
            title='Deletion Pending Gallery', event_slug='deletion-pending-gallery',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.', gallery_is_public=True,
        )
        public_id = f'{cloudinary_folder("events")}/deletion-pending/photo'
        image = EventGalleryImage.objects.create(
            event=event, asset_id='deletion-pending-asset', public_id=public_id,
            secure_url=f'https://res.cloudinary.com/oef/image/upload/v1/{public_id}.jpg',
            original_filename='deletion-pending.jpg', width=1600, height=900,
            is_public=True, uploaded_by=self.writer,
        )
        asset, _ = adopt_event_gallery_image(image, self.writer)
        image.deletion_status = EventGalleryImage.DeletionStatus.PENDING
        image.save(update_fields=('deletion_status',))
        grant(self.writer, 'submit_article')
        article = Article.objects.create(
            article_title='Deletion pending media article',
            article_slug='deletion-pending-media-article',
            article_content='<p>Editorial copy.</p>',
            article_author=self.writer,
            feature_media=asset,
        )

        self.assertEqual(self.client.get(self.event_library_url).json()['assets'], [])
        with self.assertRaisesMessage(ValidationError, 'now private'):
            submit_article(article, self.writer)

    @override_settings(OEF_EVENT_MEDIA_LIBRARY_PAGE_SIZE=1)
    def test_event_library_is_paginated_and_all_public_images_are_reachable(self):
        event = Events.objects.create(
            title='Paginated Gallery', event_slug='paginated-gallery',
            event_date='2026-08-25', location='Akure', time='10:00',
            content='Community outreach.', gallery_is_public=True,
        )
        for index in range(2):
            EventGalleryImage.objects.create(
                event=event,
                asset_id=f'page-asset-{index}',
                public_id=f'{cloudinary_folder("events")}/page/photo-{index}',
                secure_url=f'https://res.cloudinary.com/oef/image/upload/page-{index}.jpg',
                original_filename=f'page-{index}.jpg',
                is_public=True,
                uploaded_by=self.writer,
            )

        first = self.client.get(self.event_library_url)
        second = self.client.get(first.json()['next_url'])

        self.assertEqual(len(first.json()['assets']), 1)
        self.assertEqual(first.json()['total_count'], 2)
        self.assertIsNotNone(first.json()['next_url'])
        self.assertEqual(len(second.json()['assets']), 1)
        self.assertIsNone(second.json()['next_url'])

    @patch('blog.media.cloudinary.uploader.upload')
    def test_authenticated_writer_can_upload_a_valid_image(self, upload):
        upload.return_value = {
            'asset_id': 'asset-1',
            'public_id': f'{cloudinary_folder("editorial")}/editorial-1',
            'secure_url': (
                'https://res.cloudinary.com/oef/image/upload/v1/'
                f'{cloudinary_folder("editorial")}/editorial-1.png'
            ),
            'format': 'png',
            'width': 24,
            'height': 16,
            'bytes': 91,
        }
        response = self.client.post(self.url, {
            'image': make_image(),
            'alt_text': 'Volunteers arranging relief materials',
            'caption': 'Preparation before the outreach.',
        })

        self.assertEqual(response.status_code, 201)
        asset = MediaAsset.objects.get()
        self.assertEqual(asset.uploaded_by, self.writer)
        self.assertEqual(asset.alt_text, 'Volunteers arranging relief materials')
        self.assertFalse(asset.approved_for_publication)
        self.assertEqual(response.json()['url'], asset.transformed_url('inline'))
        self.assertEqual(response.json()['feature_url'], asset.feature_url)
        self.assertNotIn('variants', response.json())

    def test_writer_can_generate_fixed_ratio_crop_for_own_asset(self):
        asset = make_media_asset(self.writer, 'crop')
        response = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {
                'usage': 'inline', 'crop_mode': 'fixed',
                'x': 0, 'y': 0, 'width': 32, 'height': 18,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['crop'], {
            'x': 0.0, 'y': 0.0, 'width': 32.0, 'height': 18.0,
        })
        self.assertEqual(response.json()['crop_mode'], 'fixed')
        self.assertIn(asset.public_id, response.json()['url'])

    def test_crop_coordinates_are_scaled_from_rendition_to_original_image(self):
        asset = make_media_asset(self.writer, 'scaled-feature-crop')
        asset.width = 6016
        asset.height = 4016
        asset.save(update_fields=('width', 'height'))

        response = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {
                'usage': 'feature',
                'crop_mode': 'fixed',
                'x': 0,
                'y': 60,
                'width': 1600,
                'height': 900,
                'source_width': 1600,
                'source_height': 1068,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['crop'], {
            'x': 0.0,
            'y': 225.62,
            'width': 6016.0,
            'height': 3384.27,
        })
        self.assertIn('c_crop,h_3384,w_6016,x_0,y_226', response.json()['url'])

    def test_crop_endpoint_rejects_invalid_source_dimensions(self):
        asset = make_media_asset(self.writer, 'invalid-source-dimensions')

        response = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {
                'usage': 'feature',
                'crop_mode': 'fixed',
                'x': 0,
                'y': 0,
                'width': 32,
                'height': 18,
                'source_width': 0,
                'source_height': 800,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['error'],
            'The crop source dimensions are invalid.',
        )

    def test_writer_can_generate_constrained_flexible_inline_crop(self):
        asset = make_media_asset(self.writer, 'flexible-crop')
        response = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {
                'usage': 'inline', 'crop_mode': 'flexible',
                'x': 0, 'y': 0, 'width': 600, 'height': 500,
            },
        )
        too_wide = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {
                'usage': 'inline', 'crop_mode': 'flexible',
                'x': 0, 'y': 0, 'width': 1200, 'height': 400,
            },
        )
        feature_flexible = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {
                'usage': 'feature', 'crop_mode': 'flexible',
                'x': 0, 'y': 0, 'width': 600, 'height': 500,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['crop_mode'], 'flexible')
        self.assertEqual(too_wide.status_code, 400)
        self.assertEqual(feature_flexible.status_code, 400)

    def test_crop_endpoint_rejects_wrong_ratio_and_out_of_bounds_crop(self):
        asset = make_media_asset(self.writer, 'bad-crop')
        wrong_ratio = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {'usage': 'feature', 'x': 0, 'y': 0, 'width': 10, 'height': 10},
        )
        outside = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {'usage': 'inline', 'x': 1190, 'y': 0, 'width': 24, 'height': 16},
        )
        self.assertEqual(wrong_ratio.status_code, 400)
        self.assertEqual(outside.status_code, 400)

    def test_crop_endpoint_rejects_non_finite_coordinates(self):
        asset = make_media_asset(self.writer, 'non-finite-crop')

        response = self.client.post(
            reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
            {
                'usage': 'inline', 'crop_mode': 'fixed',
                'x': 'Infinity', 'y': 0, 'width': 32, 'height': 18,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['error'],
            'The image crop coordinates are invalid.',
        )

    def test_writer_can_edit_metadata_for_own_asset(self):
        asset = make_media_asset(self.writer, 'metadata')
        response = self.client.post(
            reverse('admin:blog_mediaasset_metadata', args=(asset.pk,)),
            {'alt_text': 'Updated accessible description', 'caption': 'Updated caption'},
        )
        self.assertEqual(response.status_code, 200)
        asset.refresh_from_db()
        self.assertEqual(asset.alt_text, 'Updated accessible description')
        self.assertEqual(asset.caption, 'Updated caption')

    def test_writer_cannot_edit_another_users_asset(self):
        grant(self.writer, 'change_mediaasset')
        owner = make_user('owner@example.com', 'owner')
        asset = make_media_asset(owner, 'owned-elsewhere')
        response = self.client.post(
            reverse('admin:blog_mediaasset_metadata', args=(asset.pk,)),
            {'alt_text': 'Unauthorised change'},
        )
        self.assertEqual(response.status_code, 403)

    def test_reviewer_permission_can_edit_another_users_asset(self):
        reviewer = make_user('media-reviewer@example.com', 'mediareviewer')
        grant(reviewer, 'view_mediaasset', 'change_mediaasset', 'approve_mediaasset')
        asset = make_media_asset(self.writer, 'reviewed-metadata')
        self.client.force_login(reviewer)

        response = self.client.post(
            reverse('admin:blog_mediaasset_metadata', args=(asset.pk,)),
            {'alt_text': 'Reviewer-approved description'},
        )

        self.assertEqual(response.status_code, 200)

    @patch('blog.media.cloudinary.uploader.upload')
    def test_upload_rejects_missing_alt_text_before_cloudinary(self, upload):
        response = self.client.post(self.url, {'image': make_image(), 'alt_text': ''})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Alternative text is required', response.json()['error'])
        upload.assert_not_called()

    @patch('blog.media.cloudinary.uploader.destroy')
    @patch('blog.media.cloudinary.uploader.upload')
    def test_upload_rejects_unapproved_provider_url(self, upload, destroy):
        upload.return_value = {
            'asset_id': 'asset-unsafe',
            'public_id': f'{cloudinary_folder("editorial")}/unsafe',
            'secure_url': 'https://example.com/unsafe.png',
            'format': 'png',
            'width': 24,
            'height': 16,
            'bytes': 91,
        }

        response = self.client.post(self.url, {
            'image': make_image(),
            'alt_text': 'A valid description',
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(MediaAsset.objects.exists())
        destroy.assert_called_once_with(
            f'{cloudinary_folder("editorial")}/unsafe',
            resource_type='image',
            type='upload',
        )

    @patch('blog.media.cloudinary.uploader.destroy')
    @patch('blog.media.cloudinary.uploader.upload')
    def test_upload_rejects_provider_public_id_url_mismatch(self, upload, destroy):
        expected_public_id = f'{cloudinary_folder("editorial")}/expected'
        upload.return_value = {
            'asset_id': 'asset-mismatch',
            'public_id': expected_public_id,
            'secure_url': (
                'https://res.cloudinary.com/oef/image/upload/v1/'
                f'{cloudinary_folder("editorial")}/different.png'
            ),
            'format': 'png', 'width': 24, 'height': 16, 'bytes': 91,
        }

        response = self.client.post(self.url, {
            'image': make_image(), 'alt_text': 'A valid description',
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(MediaAsset.objects.exists())
        destroy.assert_called_once_with(
            expected_public_id, resource_type='image', type='upload',
        )

    @patch('blog.media.cloudinary.uploader.upload')
    def test_upload_rejects_svg_and_spoofed_image_content(self, upload):
        svg = SimpleUploadedFile(
            'unsafe.svg',
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            content_type='image/png',
        )
        response = self.client.post(self.url, {'image': svg, 'alt_text': 'Unsafe image'})
        self.assertEqual(response.status_code, 400)
        upload.assert_not_called()

    @patch('blog.media.cloudinary.uploader.upload')
    @patch('blog.media.Image.open')
    def test_upload_rejects_decompression_bomb_images(self, image_open, upload):
        image_open.side_effect = Image.DecompressionBombError('unsafe dimensions')

        response = self.client.post(self.url, {
            'image': make_image('oversized.png'),
            'alt_text': 'An oversized image',
        })

        self.assertEqual(response.status_code, 400)
        upload.assert_not_called()

    def test_user_without_media_permission_is_denied(self):
        outsider = make_user('outsider@example.com', 'outsider')
        self.client.force_login(outsider)
        response = self.client.post(self.url, {
            'image': make_image(),
            'alt_text': 'Description',
        })
        self.assertEqual(response.status_code, 403)
