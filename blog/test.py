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
            article_slug='test-article',
            article_content='Article body',
            article_author=self.author,
            is_published=True,
            publish_date=timezone.datetime(2026, 7, 7, tzinfo=timezone.utc),
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
