from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from django.test import Client, SimpleTestCase, TestCase, override_settings

from ext_libs.python_social.backends import LinkedinOAuth2


class LinkedinOAuth2TestCase(SimpleTestCase):
    redirect_uri = (
        'https://oluwafemiebenezerfoundation.org/'
        'social-auth/complete/linkedin-oauth2/'
    )

    def build_backend(self, configured_redirect_uri):
        strategy = MagicMock()
        strategy.request_data.return_value = {'code': 'authorization-code'}
        strategy.absolute_uri.side_effect = (
            lambda uri: uri
            if uri.startswith('http')
            else 'https://www.oluwafemiebenezerfoundation.org' + uri
        )

        settings = {
            'KEY': 'linkedin-client-id',
            'SECRET': 'linkedin-client-secret',
            'REDIRECT_URI': configured_redirect_uri,
        }
        strategy.setting.side_effect = (
            lambda name, default=None, backend=None: settings.get(name, default)
        )
        return LinkedinOAuth2(
            strategy,
            '/social-auth/complete/linkedin-oauth2/',
        )

    def test_configured_redirect_uri_is_used_for_both_oauth_steps(self):
        backend = self.build_backend(self.redirect_uri)

        self.assertEqual(backend.auth_params()['redirect_uri'], self.redirect_uri)
        self.assertEqual(
            backend.auth_complete_params()['redirect_uri'],
            self.redirect_uri,
        )

    def test_request_host_callback_remains_the_fallback(self):
        backend = self.build_backend(None)

        self.assertEqual(
            backend.get_redirect_uri(),
            'https://www.oluwafemiebenezerfoundation.org/'
            'social-auth/complete/linkedin-oauth2/',
        )


@override_settings(
    ALLOWED_HOSTS=['www.oluwafemiebenezerfoundation.org'],
    SOCIAL_AUTH_LINKEDIN_OAUTH2_KEY='linkedin-client-id',
    SOCIAL_AUTH_LINKEDIN_OAUTH2_SECRET='linkedin-client-secret',
)
class LinkedinOAuth2BeginFlowTestCase(TestCase):
    def test_begin_flow_uses_non_www_redirect_uri(self):
        response = Client().post(
            '/social-auth/login/linkedin-oauth2/',
            HTTP_HOST='www.oluwafemiebenezerfoundation.org',
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        authorization_url = urlparse(response.url)
        self.assertEqual(authorization_url.netloc, 'www.linkedin.com')
        self.assertEqual(
            parse_qs(authorization_url.query)['redirect_uri'],
            [
                'https://oluwafemiebenezerfoundation.org/'
                'social-auth/complete/linkedin-oauth2/'
            ],
        )
