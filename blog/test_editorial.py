from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from blog.forms import ArticleForm
from blog.media import (editorial_public_id_from_url,
                        editorial_public_ids_from_urls)
from blog.models import Article, ArticleRevision, MediaAsset
from blog.workflow import (approve_revision, publish_article_directly,
                           request_changes, submit_article)
from utils.cloudinary_paths import cloudinary_folder


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
        wrong_environment = public_id.replace('/test/', '/production/')
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
        self.assertEqual(revision.number, 1)
        self.assertEqual(self.article.pending_revision, revision)
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.IN_REVIEW)
        revision.title = 'Changed after submission'
        with self.assertRaisesMessage(ValidationError, 'immutable'):
            revision.save()

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

    def test_reviewer_publishes_specific_revision_and_writer_cannot_self_approve(self):
        revision = submit_article(self.article, self.writer)
        with self.assertRaises(PermissionDenied):
            approve_revision(revision, self.writer)

        approve_revision(revision, self.reviewer)
        self.article.refresh_from_db()
        revision.refresh_from_db()
        self.assertTrue(self.article.is_published)
        self.assertEqual(self.article.published_revision, revision)
        self.assertEqual(revision.status, ArticleRevision.Status.APPROVED)

    def test_editing_after_publication_does_not_replace_live_copy(self):
        first_revision = submit_article(self.article, self.writer)
        approve_revision(first_revision, self.reviewer)

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
        self.assertEqual(article.pending_revision.number, 1)
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
        self.assertEqual(revision.status, ArticleRevision.Status.APPROVED)
        self.assertEqual(revision.created_by, superuser)
        self.assertEqual(revision.reviewed_by, superuser)

    def test_non_superuser_cannot_publish_directly(self):
        with self.assertRaises(PermissionDenied):
            publish_article_directly(self.article, self.reviewer)

    def test_superuser_article_form_exposes_publish_now(self):
        superuser = get_user_model().objects.create_superuser(
            email='publisher-ui@example.com',
            username='publisher-ui',
            password='test-pass-123',
        )
        self.client.force_login(superuser)

        response = self.client.get(reverse('admin:blog_article_add'))

        self.assertContains(response, 'Publish now')
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
        self.assertEqual(self.article.workflow_status, Article.WorkflowStatus.PUBLISHED)
        self.assertTrue(self.article.is_published)

    def test_published_article_full_revision_cycle_keeps_old_copy_live_until_approval(self):
        first = submit_article(self.article, self.writer)
        approve_revision(first, self.reviewer)
        self.article.refresh_from_db()

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

        self.article.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, ArticleRevision.Status.SUPERSEDED)
        self.assertEqual(second.status, ArticleRevision.Status.CHANGES_REQUESTED)
        self.assertEqual(self.article.published_revision, third)
        self.assertEqual(self.article.public_title, 'Reviewed replacement title')
        self.assertEqual(self.article.public_content, '<p>Reviewed replacement body.</p>')

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
