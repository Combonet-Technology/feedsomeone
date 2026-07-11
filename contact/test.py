from unittest.mock import Mock, patch

from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse

from contact.forms import NewsletterForm
from ext_libs.email_service import (EmailProviderError, send_email,
                                    upsert_newsletter_contact)
from user.models import Lead


def newsletter_payload(email="subscriber@example.com"):
    return {
        "email": email,
        "phonenumber": "+234812345678",
    }


class NewsletterFormTests(TestCase):
    def test_accepts_email_field(self):
        form = NewsletterForm(data={"email": "subscriber@example.com"})

        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_duplicate_lead(self):
        Lead.objects.create(email="subscriber@example.com")

        form = NewsletterForm(data={"email": "subscriber@example.com"})

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class NewsletterSignupTests(TestCase):
    @override_settings(
        BREVO_SENDER_EMAIL="updates@example.com",
        BREVO_CONTACT_RECIPIENTS=["contact@example.com"],
    )
    @patch("contact.views.send_email")
    @patch("contact.views.upsert_newsletter_contact")
    def test_subscribes_lead_and_syncs_to_brevo(self, mock_upsert_contact, mock_send_email):
        response = self.client.post(reverse("newsletter"), newsletter_payload(), follow=True)

        self.assertRedirects(response, "/")
        lead = Lead.objects.get(email="subscriber@example.com")
        self.assertEqual(lead.stage, "Subscriber")
        self.assertEqual(lead.source, "Website")
        mock_upsert_contact.assert_called_once_with(
            "subscriber@example.com",
            attributes={"SOURCE": "Website"},
        )
        mock_send_email.assert_called_once()
        self.assertEqual(mock_send_email.call_args.kwargs["source"], "updates@example.com")
        self.assertEqual(mock_send_email.call_args.kwargs["destination"], "subscriber@example.com")
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertIn("Thank you for subscribing to OEF updates.", messages)

    @patch("contact.views.send_email", side_effect=EmailProviderError("provider down"))
    @patch("contact.views.upsert_newsletter_contact")
    def test_keeps_local_subscription_when_brevo_email_fails(self, mock_upsert_contact, mock_send_email):
        response = self.client.post(reverse("newsletter"), newsletter_payload(), follow=True)

        self.assertRedirects(response, "/")
        self.assertTrue(Lead.objects.filter(email="subscriber@example.com", stage="Subscriber").exists())
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertIn("You have been subscribed, but the welcome email could not be sent yet.", messages)


class BrevoEmailServiceTests(TestCase):
    @override_settings(
        BREVO_API_KEY="test-api-key",
        BREVO_API_BASE_URL="https://api.brevo.com/v3",
        BREVO_SENDER_EMAIL="updates@example.com",
        BREVO_SENDER_NAME="OEF",
        BREVO_REPLY_TO_EMAIL="reply@example.com",
        BREVO_TIMEOUT_SECONDS=3,
    )
    @patch("ext_libs.email_service.requests.post")
    def test_send_email_posts_brevo_transactional_payload(self, mock_post):
        mock_post.return_value = Mock(status_code=201, text='{"messageId":"abc"}')

        self.assertTrue(send_email("person@example.com", "Subject", "<p>Hello</p>"))

        mock_post.assert_called_once_with(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": "test-api-key",
                "content-type": "application/json",
            },
            json={
                "sender": {"name": "OEF", "email": "updates@example.com"},
                "to": [{"email": "person@example.com"}],
                "subject": "Subject",
                "replyTo": {"email": "reply@example.com"},
                "htmlContent": "<p>Hello</p>",
            },
            timeout=3,
        )

    @override_settings(
        BREVO_API_KEY="test-api-key",
        BREVO_API_BASE_URL="https://api.brevo.com/v3",
        BREVO_NEWSLETTER_LIST_ID=12,
        BREVO_TIMEOUT_SECONDS=3,
    )
    @patch("ext_libs.email_service.requests.post")
    def test_upsert_newsletter_contact_posts_brevo_contact_payload(self, mock_post):
        mock_post.return_value = Mock(status_code=201, text='{"id":21}')

        self.assertTrue(upsert_newsletter_contact("person@example.com", attributes={"SOURCE": "Website"}))

        mock_post.assert_called_once_with(
            "https://api.brevo.com/v3/contacts",
            headers={
                "accept": "application/json",
                "api-key": "test-api-key",
                "content-type": "application/json",
            },
            json={
                "email": "person@example.com",
                "updateEnabled": True,
                "attributes": {"SOURCE": "Website"},
                "listIds": [12],
            },
            timeout=3,
        )
