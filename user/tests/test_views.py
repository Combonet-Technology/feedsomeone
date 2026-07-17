import importlib
import json
from unittest import mock
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.forms import ImageField
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.test.client import Client, RequestFactory
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from social_core.exceptions import AuthCanceled

from user import views
from user.forms import UsernameForm, UserRegistrationForm
from user.management.services import SiteService
from user.mocks import MockUser, RegisterUser, mock_decorator
from user.models import Volunteer
from user.token import account_activation_token
from user.views import (VolunteerDetailView, VolunteerListView,
                        check_username_availability, reset_from_source)
from utils.auth import get_user
from utils.enums import EthnicityEnum, ReligionEnum, StateEnum
from utils.views import generate_uidb64

User = get_user_model()


class ProfileViewTestCase(TestCase):
    def setUp(self):
        self.host = 'mail.com'
        self.site = SiteService.add_site(domain=self.host, name='Example Site')
        self.client = Client()
        self.user = User.objects.create_user(email='test@mail.com', password='testpassword')
        self.client.login(email='test@mail.com', password='testpassword')
        self.volunteer = Volunteer.objects.create(phone_number='123456789', state_of_residence=StateEnum.ANAMBRA.value)
        self.volunteer.user = self.user
        self.volunteer.save()
        self.url = reverse('profile')

    def test_profile_get_request(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profile.html')
        self.assertEqual(response.context['user'], self.volunteer)

    def test_post_request_valid_form(self):
        image_file = mock.MagicMock(spec=ImageField)
        image_file.name = 'test_image.jpg'
        image_file.content_type = 'image/jpeg'

        form_data = {
            'phone_number': '1234567890',
            'profession': 'Teacher',
            'ethnicity': EthnicityEnum.YORUBA.name,
            'religion': ReligionEnum.CHRISTIANITY.name,
            'state_of_residence': StateEnum.ANAMBRA.name,
            'short_bio': 'I am a volunteer.',
        }
        response = self.client.post(self.url, data=form_data, files=image_file, follow=True)
        # self.assertEqual(len(response.context['messages']), 1)
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(list(messages)[0]), f'Account for {self.volunteer.user} updated Successfully!')
        self.assertEqual(response.status_code, 200)

    def test_post_request_invalid_form(self):
        form_data = {
        }
        response = self.client.post(self.url, data=form_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user_update_form'].is_bound)
        self.assertFalse(response.context['user_update_form'].is_valid())

    def test_get_request_other_user(self):
        self.client.logout()
        response = self.client.get(self.url, HTTP_HOST=self.host)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/login/?next=/volunteers/profile/')

    def test_post_request_unauthenticated(self):
        self.client.logout()
        form_data = {}
        response = self.client.post(self.url, HTTP_HOST=self.host, data=form_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/login/?next=/volunteers/profile/')


class LogoutViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='logout@example.com',
            password='testpassword',
        )
        self.url = reverse('logout')
        self.client.force_login(self.user)

    def test_get_does_not_log_out_authenticated_user(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    def test_post_logs_out_authenticated_user(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_controls_are_post_forms(self):
        response = self.client.get(reverse('mainsite:homepage'))
        content = response.content.decode()

        self.assertEqual(content.count(f'action="{self.url}"'), 2)
        self.assertNotContains(response, f'href="{self.url}"')
        self.assertGreaterEqual(content.count('name="csrfmiddlewaretoken"'), 2)

    def test_logout_post_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertIn('_auth_user_id', csrf_client.session)


class ActivateTestCase(TestCase):
    def setUp(self):
        self.host = 'google.com'
        self.site = SiteService.add_site(domain=self.host, name='Example Site')
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(username='testuser', email='test@google.com')
        self.user.is_active = False
        self.user.save()
        self.token = account_activation_token.make_token(self.user)

    def test_valid_activation(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(reverse('activate', kwargs={'uidb64': uidb64, 'token': self.token}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_invalid_uidb(self):
        response = self.client.get(reverse('activate', args=('invalid_uidb64', self.token)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activation link is invalid or expired!')

    def test_invalid_token(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(reverse('activate', args=(uidb64, 'invalid_token')))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activation link is invalid or expired!')

    def test_active_user(self):
        self.user.is_active = False
        self.user.save()
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(reverse('activate', args=(uidb64, self.token)), follow=True, HTTP_HOST=self.host)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Activation link is invalid or expired!')
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_activate_non_existent_user(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.user.delete()
        response = self.client.get(reverse('activate', kwargs={'uidb64': uidb64, 'token': self.token}))
        self.assertContains(response, 'Activation link is invalid or expired!')


@patch('user.views.get_current_site')
@patch('user.views.send_email')
class RegisterTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = RegisterUser()

    def test_post_request(self, mock_send_email, mock_get_current_site):
        mock_send_email.return_value = True
        mock_get_current_site.return_value.domain = 'example.com'
        data = self.user.spawn
        data[settings.HONEYPOT_FIELD_NAME] = settings.HONEYPOT_VALUE
        response = self.client.post(reverse('register'), data)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'thank-you.html')
        self.assertTrue(all(True if key in response.context else False for key in ['subject', 'msg', 'title']))
        created_user = User.objects.get(email=self.user.email)
        self.assertFalse(created_user.is_active)
        self.assertTrue(created_user.check_password(self.user.password))
        mock_send_email.assert_called_once()

    def test_get_request(self, mock_send_email, mock_get_current_site):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')
        self.assertIsInstance(response.context['forms'], UserRegistrationForm)
        self.assertFalse(response.context['forms'].is_bound)
        self.assertEqual(list(response.context['forms'].fields), ['email', 'password'])
        for backend in ['twitter', 'facebook', 'linkedin-oauth2', 'google-oauth2']:
            self.assertContains(response, reverse('social:begin', args=[backend]))
        self.assertNotContains(response, 'google.com/recaptcha/api.js')

    def test_tampered_honeypot_is_rejected(self, mock_send_email, mock_get_current_site):
        data = self.user.spawn
        data[settings.HONEYPOT_FIELD_NAME] = 'tampered'
        response = self.client.post(reverse('register'), data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email=self.user.email).exists())
        mock_send_email.assert_not_called()

    @override_settings(REGISTRATION_RATE_LIMIT=1, REGISTRATION_RATE_LIMIT_WINDOW=3600)
    def test_rate_limits_repeated_registration_attempts(
            self, mock_send_email, mock_get_current_site):
        data = {settings.HONEYPOT_FIELD_NAME: settings.HONEYPOT_VALUE}

        first_response = self.client.post(reverse('register'), data, REMOTE_ADDR='203.0.113.20')
        second_response = self.client.post(reverse('register'), data, REMOTE_ADDR='203.0.113.20')

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)
        self.assertTemplateUsed(second_response, 'robot_response.html')

    def test_invalid_post_forms(self, mock_send_email, mock_get_current_site):
        response = self.client.post(
            reverse('register'),
            {settings.HONEYPOT_FIELD_NAME: settings.HONEYPOT_VALUE},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')
        self.assertIsInstance(response.context['forms'], UserRegistrationForm)
        self.assertTrue(response.context['forms'].is_bound)
        self.assertFalse(response.context['forms'].is_valid())
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(list(messages)[0]), 'INVALID USER INPUTS')


class VolunteerTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_mock = MockUser()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(username='testuser', email='test@google.com')
        self.url = reverse('volunteer-list')
        self.factory = RequestFactory()
        self.view = VolunteerListView

    def test_get_template_names_normal(self):
        view = self.view(request=self.factory.get('/volunteer/'))
        template_names = view.get_template_names()
        self.assertIsInstance(template_names, list)
        self.assertIn('user/userprofile_list.html', template_names)

    def test_get_template_names_ajax(self):
        view = self.view(request=self.factory.get('/volunteer/', HTTP_X_REQUESTED_WITH='XMLHttpRequest'))
        view.queryset = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        template_names = view.get_template_names()
        self.assertIsInstance(template_names, list)
        self.assertIn('user/userprofile_ajax.html', template_names)

    def test_volunteer_detail_context_object_name(self):
        id = self.user.pk
        request = RequestFactory().get(f'/volunteer/{id}')
        view = VolunteerDetailView(request=request, kwargs={'pk': id})
        context_object_name = view.get_context_object_name(view.get_object())
        self.assertEqual(context_object_name, 'volunteer')

    def test_paginate_queryset(self):
        queryset = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        request = RequestFactory().get('/volunteers/', {'page': 1})
        view = VolunteerListView(request=request)
        paginated_queryset, page, results, is_paginated = view.paginate_queryset(queryset, view.paginate_by)
        self.assertEqual(len(results), view.paginate_by)
        self.assertIsInstance(paginated_queryset, Paginator)

    def test_get_queryset(self):
        Volunteer.objects.create(user=self.user, is_verified=True)
        view = self.view(request=self.client.get(self.url))
        expected_queryset = list(Volunteer.objects.all())
        actual_queryset = list(view.get_queryset())

        self.assertEqual(actual_queryset, expected_queryset)


class CheckUsernameAvailabilityTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(username='existing_user', email='test@google.com')

    def test_username_available(self):
        data = {'username': 'new_username'}
        request = self.factory.post(reverse('check_username_availability'), data,
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        request.user = self.user
        response = check_username_availability(request)
        content = json.loads(response.content)

        # Assert that the response is indicating that the username is available
        self.assertEqual(response.status_code, 200)
        self.assertEqual(content, {'available': True})

    def test_username_unavailable(self):
        data = {'username': 'existing_user'}
        request = self.factory.post(reverse('check_username_availability'), data,
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        request.user = self.user
        response = check_username_availability(request)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(content, {'available': False})

    def test_invalid_request(self):
        data = {}
        request = self.factory.post(reverse('check_username_availability'), data)
        response = check_username_availability(request)

        self.assertEqual(response.status_code, 400)


class CreateUsernameTestCase(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(username='testuser', email='test@google.com')
        self.url = reverse('create_username')
        self.client = Client()
        self.client.force_login(self.user)

    def test_get_request(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], UsernameForm)

    def test_post_request_valid_form(self):
        data = {'username': 'new_username'}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, data['username'])

    def test_post_request_invalid_form(self):
        data = {'username': ''}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], UsernameForm)
        self.assertFalse(response.context['form'].is_valid())


class ResetFromSourceTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='testpassword')
        self.uidb64 = generate_uidb64(self.user)

    def test_reset_from_source_with_token_and_uidb64(self):
        token = 'fake_token'
        user = get_user(uidb64=self.uidb64)
        response = self.client.get(reverse('create_private_pass', args=[token, self.uidb64]))
        self.client.force_login(user=user)

        # Call the function
        already_logged, motive, found_user = reset_from_source(response.wsgi_request, token, self.uidb64)

        # Assert the results
        self.assertFalse(already_logged)
        self.assertEqual(motive, 'Change')
        self.assertEqual(found_user, user)

    def test_reset_from_source_with_authenticated_user(self):
        self.client.force_login(user=self.user)
        response = self.client.get(reverse('create_private_pass'))

        # Call the function
        already_logged, motive, found_user = reset_from_source(response.wsgi_request, None, None)

        # Assert the results
        self.assertTrue(already_logged)
        self.assertEqual(motive, 'Set')
        self.assertEqual(found_user, self.user)

    def test_reset_from_source_without_token_and_uidb64_and_unauthenticated_user(self):
        # Set up the test data
        response = self.client.get(reverse('create_private_pass'))

        # Call the function
        already_logged, motive, found_user = reset_from_source(response.wsgi_request, None, None)

        # Assert the results
        self.assertFalse(already_logged)
        self.assertEqual(motive, '')
        self.assertIsNone(found_user)


def test_set_password_view(self):
    pass


@patch('ext_libs.python_social.social_auth_backends.do_complete')
class SocialAuthCompleteTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(username='testuser', email='test@google.com')
        self.request = self.factory.get(reverse('complete', kwargs={'backend': 'test'}))
        self.request.session = {}
        self.request.backend = MagicMock()
        self.request.user = self.user

        def kill_patches():  # Create a cleanup callback that undoes our patches
            patch.stopall()  # Stops all patches started with start()
            importlib.reload(views)  # Reload our UUT module which restores the original decorator

        self.addCleanup(kill_patches)
        patch('social_django.utils.psa', mock_decorator).start()
        importlib.reload(views)

    def test_social_auth_complete_auth_canceled(self, mock_do_complete):
        mock_do_complete.side_effect = AuthCanceled(self.request.backend)
        response = views.social_auth_complete(self.request, backend='backend')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))

    def test_social_auth_complete_other_exception(self, mock_do_complete):
        mock_do_complete.side_effect = Exception('Some error')
        response = views.social_auth_complete(self.request, backend='backend')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))

    def test_social_auth_complete_returns_non_redirect_response(self, mock_do_complete):
        mock_do_complete.return_value = HttpResponse(status=200)
        response = views.social_auth_complete(self.request, backend='backend')
        self.assertEqual(response.status_code, 200)

    def test_social_auth_complete_creates_missing_volunteer_profile(self, mock_do_complete):
        mock_do_complete.return_value.status_code = 302
        response = views.social_auth_complete(self.request, backend='backend')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('create_private_pass'))
        self.assertTrue(Volunteer._base_manager.filter(user=self.user).exists())

    def test_social_auth_complete_successful_user_without_password(self, mock_do_complete):
        mock_do_complete.return_value.status_code = 302
        response = views.social_auth_complete(self.request, backend='backend')
        mock_do_complete.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('create_private_pass'))

    def test_social_auth_complete_successful_user_with_password(self, mock_do_complete):
        mock_do_complete.return_value.status_code = 302
        Volunteer.objects.create(user=self.user, is_verified=True)
        self.request.user.set_password('Password123.')
        response = views.social_auth_complete(self.request, backend='backend')
        mock_do_complete.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('profile'))

    # def test_recaptcha_success(self):
    #     request = RequestFactory()
    #
    # def test_recaptcha_failure(self):
    #     pass
