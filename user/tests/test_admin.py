from django.contrib import admin
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from user.admin import UserProfileAdmin
from user.forms import UserProfileAdminCreationForm
from user.models import UserProfile


class UserProfileAdminTests(TestCase):
    def test_admin_creation_form_hashes_password(self):
        form = UserProfileAdminCreationForm(
            data={
                'email': 'staff@example.com',
                'first_name': 'Staff',
                'last_name': 'Member',
                'password1': 'A-secure-test-password-2468',
                'password2': 'A-secure-test-password-2468',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.check_password('A-secure-test-password-2468'))

    def test_admin_exposes_staff_and_group_controls(self):
        model_admin = UserProfileAdmin(UserProfile, admin.site)
        access_fields = model_admin.fieldsets[2][1]['fields']

        self.assertIn('is_staff', access_fields)
        self.assertIn('groups', access_fields)
        self.assertIn('user_permissions', access_fields)

    def test_superuser_can_create_grouped_staff_account_in_admin(self):
        owner = UserProfile.objects.create_superuser(
            email='owner@example.com',
            password='owner-test-password',
        )
        group, _ = Group.objects.get_or_create(name='Recruitment Manager')
        self.client.force_login(owner)

        response = self.client.post(
            reverse('admin:user_userprofile_add'),
            {
                'email': 'recruitment@example.com',
                'first_name': 'Recruitment',
                'last_name': 'Manager',
                'password1': 'A-secure-test-password-2468',
                'password2': 'A-secure-test-password-2468',
                'is_active': 'on',
                'is_staff': 'on',
                'groups': [str(group.pk)],
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 302)
        staff = UserProfile.objects.get(email='recruitment@example.com')
        self.assertTrue(staff.is_active)
        self.assertTrue(staff.is_staff)
        self.assertTrue(staff.check_password('A-secure-test-password-2468'))
        self.assertTrue(staff.groups.filter(pk=group.pk).exists())
