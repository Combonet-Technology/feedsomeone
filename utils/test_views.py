from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from utils.views import verify_recaptcha


@override_settings(
    RECAPTCHA_PRIVATE_KEY='private-key',
    RECAPTCHA_MIN_SCORE=0.5,
    RECAPTCHA_TIMEOUT_SECONDS=2,
)
class VerifyRecaptchaTests(SimpleTestCase):
    @patch('utils.views.requests.post')
    def test_accepts_matching_successful_high_score_token(self, mock_post):
        response = Mock()
        response.json.return_value = {
            'success': True,
            'action': 'registrationForm',
            'score': 0.9,
        }
        mock_post.return_value = response

        self.assertTrue(verify_recaptcha('token', remote_ip='203.0.113.10'))
        mock_post.assert_called_once_with(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': 'private-key',
                'response': 'token',
                'remoteip': '203.0.113.10',
            },
            timeout=2,
        )

    @patch('utils.views.requests.post')
    def test_rejects_success_key_when_value_is_false(self, mock_post):
        response = Mock()
        response.json.return_value = {
            'success': False,
            'action': 'registrationForm',
            'score': 0.9,
        }
        mock_post.return_value = response

        self.assertFalse(verify_recaptcha('token'))

    @patch('utils.views.requests.post')
    def test_rejects_wrong_action_or_low_score(self, mock_post):
        response = Mock()
        response.json.return_value = {
            'success': True,
            'action': 'otherAction',
            'score': 0.1,
        }
        mock_post.return_value = response

        self.assertFalse(verify_recaptcha('token'))

    @patch('utils.views.requests.post')
    def test_rejects_malformed_score(self, mock_post):
        response = Mock()
        response.json.return_value = {
            'success': True,
            'action': 'registrationForm',
            'score': 'not-a-number',
        }
        mock_post.return_value = response

        self.assertFalse(verify_recaptcha('token'))

    @patch('utils.views.requests.post', side_effect=requests.Timeout)
    def test_fails_closed_on_provider_timeout(self, _mock_post):
        self.assertFalse(verify_recaptcha('token'))

    def test_rejects_missing_token_without_network_request(self):
        self.assertFalse(verify_recaptcha(''))
