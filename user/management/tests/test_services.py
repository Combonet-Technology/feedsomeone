from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase

from user.management.services import CreateSuperUserService, SiteService

User = get_user_model()


class SiteServiceTestCase(TestCase):
    def setUp(self):
        self.site_name = 'Random Example Site'
        self.site_domain = 'google.com'

    def test_add_site(self):
        SiteService.add_site(name=self.site_name, domain=self.site_domain)
        site = Site.objects.get(name=self.site_name, domain=self.site_domain)
        self.assertEqual(site.name, self.site_name)
        self.assertEqual(site.domain, self.site_domain)

    def test_remove_site(self):
        SiteService.add_site(name=self.site_name, domain=self.site_domain)
        SiteService.remove_site(domain=self.site_domain)
        # confirm removal and non-existent domain
        with self.assertRaises(ObjectDoesNotExist):
            Site.objects.get(name=self.site_name, domain=self.site_domain)

    def tearDown(self) -> None:
        Site.objects.all().delete()


class CreateSuperUserServiceTestCase(TestCase):
    def test_create_superuser(self):
        superuser_email = 'admin@example.com'
        superuser_password = 'password'

        CreateSuperUserService.create_superuser(email=superuser_email, password=superuser_password)

        superuser = User.objects.get(email=superuser_email)
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_staff)

    def test_recover_superuser_password_existing_user(self):
        superuser_email = 'admin@example.com'
        new_password = 'new_password'

        User.objects.create_superuser(email=superuser_email, password='password')

        CreateSuperUserService.recover_superuser_password(email=superuser_email, password=new_password)

        superuser = User.objects.get(email=superuser_email)
        self.assertTrue(superuser.check_password(new_password))

    def test_recover_superuser_password_nonexistent_user(self):
        superuser_email = 'nonuser@example.com'

        CreateSuperUserService.recover_superuser_password(email=superuser_email)

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(email=superuser_email)
