from datetime import timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from blog.forms import CommentForm
from blog.models import Article, Comments
from utils.views import custom_paginator


class ArticleFilterURLTests(TestCase):
    def test_category_and_tag_filters_have_distinct_canonical_routes(self):
        category_url = reverse(
            'article:articles-by-category', kwargs={'category': 'Briefings'},
        )
        tag_url = reverse('article:articles-by-slug', kwargs={'tag': 'impact'})

        self.assertEqual(category_url, '/article/category/Briefings/')
        self.assertEqual(tag_url, '/article/tag/impact/')
        self.assertEqual(resolve(category_url).kwargs, {'category': 'Briefings'})
        self.assertEqual(resolve(tag_url).kwargs, {'tag': 'impact'})


class CommentFormTests(TestCase):
    def test_accepts_blank_website(self):
        form = CommentForm(data={
            'name': 'Reader',
            'email': 'reader@example.com',
            'body': 'Helpful article.',
            'website': '',
        })

        self.assertTrue(form.is_valid(), form.errors)


class ArticleListRenderingTests(TestCase):
    def test_rich_text_images_are_not_rendered_inside_list_previews(self):
        author = get_user_model().objects.create_user(
            email='list-author@example.com',
            username='list-author',
        )
        Article.objects.create(
            article_title='List preview test',
            article_excerpt='',
            article_slug='list-preview-test',
            article_content=(
                '<p>Text that belongs in the article preview.</p>'
                '<img src="https://example.com/private-test-image.jpg" alt="Test">'
            ),
            article_author=author,
            is_published=True,
            publish_date=timezone.now(),
        )

        response = self.client.get(reverse('article:all-articles'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Text that belongs in the article preview.')
        self.assertNotContains(response, 'https://example.com/private-test-image.jpg')


class ArticleAccessAndPaginationTests(TestCase):
    def setUp(self):
        self.author = get_user_model().objects.create_user(
            email='draft-author@example.com', username='draft-author', password='test-pass-123',
        )
        self.reader = get_user_model().objects.create_user(
            email='reader-account@example.com', username='reader-account', password='test-pass-123',
        )
        self.published = Article.objects.create(
            article_title='Public article', article_slug='public-article',
            article_content='Public body', article_author=self.author, is_published=True,
        )
        self.draft = Article.objects.create(
            article_title='Private draft', article_slug='private-draft',
            article_content='Draft body', article_author=self.author,
        )
        self.deleted = Article.objects.create(
            article_title='Deleted draft', article_slug='deleted-draft',
            article_content='Deleted body', article_author=self.author, is_deleted=True,
        )
        self.list_url = reverse(
            'article:article-by-user', kwargs={'username': self.author.username},
        )

    def test_other_user_sees_only_published_articles(self):
        self.client.force_login(self.reader)

        response = self.client.get(self.list_url)

        self.assertContains(response, self.published.article_title)
        self.assertNotContains(response, self.draft.article_title)
        self.assertNotContains(response, self.deleted.article_title)

    def test_author_sees_own_draft_but_not_deleted_articles(self):
        self.client.force_login(self.author)

        response = self.client.get(self.list_url)

        self.assertContains(response, self.published.article_title)
        self.assertContains(response, self.draft.article_title)
        self.assertNotContains(response, self.deleted.article_title)

    def test_delete_view_soft_deletes_article(self):
        self.client.force_login(self.author)

        response = self.client.post(reverse(
            'article:delete-post', kwargs={'slug': self.draft.article_slug},
        ))

        self.assertRedirects(response, reverse('article:all-articles'))
        self.draft.refresh_from_db()
        self.assertTrue(self.draft.is_deleted)

    def test_non_author_cannot_delete_article(self):
        self.client.force_login(self.reader)

        response = self.client.post(reverse(
            'article:delete-post', kwargs={'slug': self.draft.article_slug},
        ))

        self.assertEqual(response.status_code, 403)
        self.draft.refresh_from_db()
        self.assertFalse(self.draft.is_deleted)

    def test_custom_paginator_returns_page_object(self):
        request = RequestFactory().get('/article/all/', {'page': '2'})

        paginator, page_obj, results, is_paginated = custom_paginator(
            request, 3, list(range(10)),
        )

        self.assertEqual(page_obj.number, 2)
        self.assertIs(page_obj, results)
        self.assertEqual(paginator.num_pages, 4)
        self.assertTrue(is_paginated)

    def test_pagination_template_preserves_query_without_malformed_separator(self):
        page_obj = Paginator(list(range(10)), 3).page(2)

        html = render_to_string(
            'pagination.html', {'page_obj': page_obj, 'query_term': 'food support'},
        )

        self.assertIn('?query=food%20support&page=1', html)
        self.assertNotIn('&?page=', html)


class ArticleCommentViewTests(TestCase):
    def setUp(self):
        self.author = get_user_model().objects.create_user(
            email='author@example.com',
            username='author',
            first_name='OEF',
            last_name='Editor',
        )
        self.article = Article.objects.create(
            article_title='Test Article',
            article_excerpt='A concise description for readers and social previews.',
            article_slug='test-article',
            article_content='Article body',
            article_author=self.author,
            is_published=True,
            publish_date=timezone.datetime(2026, 7, 7, tzinfo=datetime_timezone.utc),
        )
        self.url = reverse('article:article_detail', kwargs={
            'year': 2026,
            'month': 7,
            'day': 7,
            'slug': self.article.article_slug,
        })

    def test_post_comment_with_blank_website_creates_moderated_comment(self):
        response = self.client.post(self.url, {
            'name': 'Reader',
            'email': 'reader@example.com',
            'body': 'Helpful article.',
            'website': '',
        }, HTTP_REFERER=self.url)

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        comment = Comments.objects.get(post=self.article)
        self.assertEqual(comment.website, '')
        self.assertFalse(comment.active)

    def test_comment_redirect_ignores_external_referer(self):
        response = self.client.post(self.url, {
            'name': 'Reader',
            'email': 'reader@example.com',
            'body': 'Helpful article.',
            'website': '',
        }, HTTP_REFERER='https://attacker.example/redirect')

        self.assertRedirects(response, self.url, fetch_redirect_response=False)

    def test_invalid_comment_without_referer_redirects_to_article(self):
        response = self.client.post(self.url, {
            'name': 'Reader',
            'email': 'reader@example.com',
            'body': '',
            'website': '',
        })

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertFalse(Comments.objects.filter(post=self.article).exists())

    def test_pending_comment_does_not_display_until_approved(self):
        Comments.objects.create(
            post=self.article,
            name='Reader',
            email='reader@example.com',
            body='Waiting for approval.',
            active=False,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Waiting for approval.')

    def test_article_without_feature_image_omits_feature_image_container(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<div class="feature-img">', html=True)

    def test_success_message_explains_moderation(self):
        response = self.client.post(self.url, {
            'name': 'Reader',
            'email': 'reader@example.com',
            'body': 'Helpful article.',
            'website': '',
        }, HTTP_REFERER=self.url, follow=True)

        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertIn('Your comment has been posted and is awaiting moderation', messages)

    def test_article_page_has_page_specific_search_and_social_metadata(self):
        response = self.client.get(self.url, HTTP_HOST='example.com')

        self.assertContains(
            response,
            '<meta name="description" content="A concise description for readers and social previews.">',
            html=True,
        )
        canonical_url = 'http://example.com' + self.url
        self.assertContains(
            response,
            f'<link rel="canonical" href="{canonical_url}">',
            html=True,
        )
        self.assertContains(response, '<meta property="og:type" content="article">', html=True)
        self.assertContains(response, '<meta property="og:title" content="Test Article">', html=True)
        self.assertContains(
            response,
            '<meta property="og:image" content="http://example.com/static/img/logo/oef-logo.svg">',
            html=True,
        )
        self.assertContains(response, '<meta name="twitter:card" content="summary_large_image">', html=True)
        self.assertContains(response, '"@type": "Article"')
        self.assertContains(response, '<h1 class="article-title">Test Article</h1>', html=True)

    def test_reply_form_is_collapsed_by_default_and_sidebar_assets_are_loaded(self):
        response = self.client.get(self.url)

        self.assertContains(response, '<details class="comment-form comment-reply" id="commentReply">', html=False)
        self.assertContains(response, '<summary id="commentReplySummary">Leave a reply</summary>', html=True)
        self.assertNotContains(response, '<details class="comment-form comment-reply" id="commentReply" open>')
        self.assertContains(response, 'css/article-detail.css')
        self.assertContains(response, 'js/article-detail.js')
