from datetime import timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from blog.forms import CommentForm
from blog.models import Article, Comments


class CommentFormTests(TestCase):
    def test_accepts_blank_website(self):
        form = CommentForm(data={
            'name': 'Reader',
            'email': 'reader@example.com',
            'body': 'Helpful article.',
            'website': '',
        })

        self.assertTrue(form.is_valid(), form.errors)


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
            '<meta property="og:image" content="http://example.com/media/feature_default.jpg">',
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
