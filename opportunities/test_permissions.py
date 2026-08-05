from importlib import import_module

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase

from opportunities.admin import VacancyApplicationAdmin
from opportunities.models import VacancyApplication
from user.models import UserProfile


class RecruitmentPermissionTests(TestCase):
    def setUp(self):
        migration = import_module(
            'opportunities.migrations.0011_create_recruitment_manager_group'
        )
        migration.create_recruitment_manager_group(apps, schema_editor=None)
        rejection_migration = import_module(
            'opportunities.migrations.0013_vacancyapplication_rejection_email'
        )
        rejection_migration.add_rejection_permission_to_recruitment_managers(
            apps,
            schema_editor=None,
        )

    def test_recruitment_manager_group_has_expected_permissions(self):
        group = Group.objects.get(name='Recruitment Manager')

        self.assertSetEqual(
            set(group.permissions.values_list('codename', flat=True)),
            {
                'view_vacancy',
                'view_vacancyapplication',
                'change_vacancyapplication',
                'send_volunteer_offer',
                'send_rejection_email',
                'view_volunteeroffer',
            },
        )

    def test_group_member_can_access_applications_and_send_offers(self):
        user = UserProfile.objects.create_user(
            email='recruitment@example.com',
            password='test-password',
            is_staff=True,
        )
        user.groups.add(Group.objects.get(name='Recruitment Manager'))

        self.assertTrue(user.has_perm('opportunities.view_vacancyapplication'))
        self.assertTrue(user.has_perm('opportunities.change_vacancyapplication'))
        self.assertTrue(user.has_perm('opportunities.send_volunteer_offer'))
        self.assertTrue(user.has_perm('opportunities.send_rejection_email'))
        self.assertFalse(user.has_perm('opportunities.delete_vacancyapplication'))

    def test_non_superuser_cannot_rewrite_applicant_submitted_fields(self):
        user = UserProfile.objects.create_user(
            email='recruitment@example.com',
            password='test-password',
            is_staff=True,
        )
        request = RequestFactory().get('/admin/opportunities/vacancyapplication/')
        request.user = user
        model_admin = VacancyApplicationAdmin(VacancyApplication, admin.site)

        readonly_fields = model_admin.get_readonly_fields(request)

        self.assertIn('full_name', readonly_fields)
        self.assertIn('email', readonly_fields)
        self.assertIn('cv', readonly_fields)
        self.assertIn('cover_letter', readonly_fields)
        self.assertNotIn('status', readonly_fields)

    def test_superuser_retains_full_application_editing(self):
        user = UserProfile.objects.create_superuser(
            email='owner@example.com',
            password='test-password',
        )
        request = RequestFactory().get('/admin/opportunities/vacancyapplication/')
        request.user = user
        model_admin = VacancyApplicationAdmin(VacancyApplication, admin.site)

        readonly_fields = model_admin.get_readonly_fields(request)

        self.assertNotIn('full_name', readonly_fields)
        self.assertNotIn('status', readonly_fields)


class VolunteerOnboardingPermissionTests(TestCase):
    def test_onboarding_group_has_narrow_application_permissions(self):
        group = Group.objects.get(name='Volunteer Onboarding')

        self.assertSetEqual(
            set(group.permissions.values_list('codename', flat=True)),
            {
                'view_vacancy',
                'view_vacancyapplication',
                'send_onboarding_email',
            },
        )

    def test_group_member_can_manage_onboarding_without_offer_permission(self):
        user = UserProfile.objects.create_user(
            email='onboarding@example.com',
            password='test-password',
            is_staff=True,
        )
        user.groups.add(Group.objects.get(name='Volunteer Onboarding'))

        self.assertTrue(user.has_perm('opportunities.view_vacancyapplication'))
        self.assertFalse(user.has_perm('opportunities.change_vacancyapplication'))
        self.assertTrue(user.has_perm('opportunities.send_onboarding_email'))
        self.assertFalse(user.has_perm('opportunities.send_volunteer_offer'))
