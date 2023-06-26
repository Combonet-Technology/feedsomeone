from unittest.mock import patch

from django.test import TestCase

from user.management.commands.create_site_url import \
    Command as create_site_command
from user.management.commands.create_super_user import \
    Command as super_user_command
from user.management.services import CreateSuperUserService, SiteService


class CreateSuperUserCommandTestCase(TestCase):
    @patch.object(CreateSuperUserService, 'create_superuser')
    def test_handle(self, mock_create_superuser):
        command = super_user_command()
        command.superuser_email = 'admin@example.com'
        command.superuser_password = 'password'

        command.handle()

        mock_create_superuser.assert_called_once_with('admin@example.com', 'password')


class CreateSiteCommandTestCase(TestCase):
    @patch.object(SiteService, 'add_site')
    def test_handle(self, mock_site_service):
        command = create_site_command()
        command.site_name = 'Example Site'
        command.site_domain = 'example.com'

        command.handle()

        mock_site_service.assert_called_once_with('Example Site', 'example.com')
