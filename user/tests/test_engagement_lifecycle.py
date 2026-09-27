from datetime import date

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from user.admin import TeamMemberAdmin
from user.models import Engagement, TeamMember, UserProfile
from user.workforce import (complete_onboarding, end_engagement,
                            start_direct_engagement, update_engagement)


class EngagementLifecycleTests(TestCase):
    def test_member_summary_shows_only_active_role_and_link_is_view_only(self):
        member_admin = TeamMemberAdmin(TeamMember, admin.site)
        self.assertIsNone(member_admin.engagement_summary(self.member))
        self.engagement.status = Engagement.Status.ACTIVE
        self.engagement.save()
        self.assertEqual(member_admin.engagement_summary(self.member), 'Writer')
        link = member_admin.engagement_link(self.member)
        self.assertIn('View engagements', link)
        self.assertNotIn('Add engagement', link)
        self.assertNotIn(reverse('admin:user_engagement_add'), link)
        end_engagement(self.engagement, self.manager)
        self.assertIsNone(member_admin.engagement_summary(self.member))

    def setUp(self):
        self.manager = UserProfile.objects.create_superuser(email='manager@example.org', password='test')
        self.account = UserProfile.objects.create_user(email='member@example.org', is_staff=True)
        self.member = TeamMember.objects.create(
            full_name='Member', primary_email=self.account.email, user=self.account,
        )
        self.engagement = Engagement.objects.create(
            team_member=self.member, role_title='Writer', start_date=date(2026, 1, 1),
        )
        self.client.force_login(self.manager)
        self.url = reverse('admin:user_engagement_change', args=[self.engagement.pk])

    def data(self, **overrides):
        return {'role_title': 'Content Writer', 'engagement_type': 'volunteer',
                'start_date': '2026-01-01', 'status': 'active', '_save': 'Save', **overrides}

    def test_team_member_start_date_has_admin_calendar_and_format_hint(self):
        response = self.client.get(reverse('admin:user_teammember_add'))
        self.assertContains(response, 'vDateField')
        self.assertContains(response, 'DateTimeShortcuts.js')
        self.assertContains(response, 'YYYY-MM-DD')

    def test_edit_and_activate_does_not_fabricate_onboarding_completion(self):
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 302)
        self.engagement.refresh_from_db()
        self.assertEqual(self.engagement.role_title, 'Content Writer')
        self.assertEqual(self.engagement.status, 'active')
        self.assertIsNone(self.engagement.onboarding_completed_at)
        self.assertEqual(self.engagement.team_member_id, self.member.pk)

    def test_end_via_detail_preserves_audit_and_backend_access(self):
        response = self.client.post(self.url, self.data(status='ended', end_date='2026-08-01'))
        self.assertEqual(response.status_code, 302)
        self.engagement.refresh_from_db()
        self.assertEqual(self.engagement.status, 'ended')
        self.assertEqual(self.engagement.end_date, date(2026, 8, 1))
        self.assertEqual(self.engagement.ended_by, self.manager)
        self.assertIsNotNone(self.engagement.ended_at)
        self.assertTrue(self.engagement.access_review_required)
        self.account.refresh_from_db()
        self.assertTrue(self.account.is_staff)

    def test_end_without_effective_date_uses_today_not_creation_date(self):
        self.assertEqual(self.client.post(self.url, self.data(status='ended')).status_code, 302)
        self.engagement.refresh_from_db()
        self.assertEqual(self.engagement.end_date, timezone.localdate())

    def test_ended_details_can_be_corrected_but_forged_status_cannot_reopen(self):
        end_engagement(self.engagement, self.manager)
        self.engagement.refresh_from_db()
        ended_at = self.engagement.ended_at
        self.assertEqual(self.client.post(self.url, self.data(end_date='2026-08-02')).status_code, 302)
        self.engagement.refresh_from_db()
        self.assertEqual(self.engagement.status, 'ended')
        self.assertEqual(self.engagement.ended_at, ended_at)
        self.assertEqual(self.engagement.end_date, date(2026, 8, 2))
        with self.assertRaisesMessage(ValidationError, 'cannot be restarted'):
            update_engagement(
                self.engagement, self.manager, role_title='Writer', engagement_type='volunteer',
                start_date=None, end_date=None, status='active',
            )

    def test_invalid_dates_and_current_end_date_are_form_errors(self):
        for values in ({'status': 'ended', 'end_date': '2025-01-01'}, {'end_date': '2026-08-01'}):
            with self.subTest(values=values):
                response = self.client.post(self.url, self.data(**values))
                self.assertEqual(response.status_code, 200)
                self.assertIn('end_date', response.context['adminform'].form.errors)
        self.engagement.refresh_from_db()
        self.assertEqual(self.engagement.status, 'onboarding')

    def test_add_requires_confirmation_and_replacement_is_audited(self):
        url = reverse('admin:user_engagement_add')
        data = self.data(team_member=self.member.pk, start_date='')
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertEqual(Engagement.objects.count(), 1)
        response = self.client.post(url, {**data, 'replace_current': 'on'})
        self.assertEqual(
            response.status_code, 302, response.context['adminform'].form.errors if response.context else '',
        )
        self.engagement.refresh_from_db()
        self.assertEqual(self.engagement.status, 'ended')
        self.assertEqual(self.engagement.ended_by, self.manager)
        self.assertFalse(self.engagement.access_review_required)
        current = self.member.engagements.exclude(status='ended').get()
        self.assertIsNone(current.start_date)
        self.assertEqual(current.status, 'active')
        self.assertEqual(self.member.engagements.count(), 2)

    def test_service_rejects_duplicate_without_confirmation(self):
        with self.assertRaisesMessage(ValidationError, 'confirm its replacement'):
            start_direct_engagement(self.member, self.manager, role_title='Writer', engagement_type='volunteer')
        self.assertEqual(Engagement.objects.count(), 1)

    def test_database_rejects_second_current_and_inverted_dates(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Engagement.objects.create(team_member=self.member, role_title='Second', status='active')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Engagement.objects.create(
                team_member=self.member, role_title='History', status='ended',
                start_date=date(2026, 2, 1), end_date=date(2026, 1, 1),
            )

    def test_failed_replacement_rolls_back_prior_ending(self):
        self.engagement.start_date = date(2099, 1, 1)
        self.engagement.save()
        with self.assertRaises(ValidationError):
            start_direct_engagement(
                self.member, self.manager, role_title='New', engagement_type='volunteer', replace_current=True,
            )
        self.engagement.refresh_from_db()
        self.assertEqual(self.engagement.status, 'onboarding')
        self.assertIsNone(self.engagement.ended_at)
        self.assertEqual(Engagement.objects.count(), 1)

    def test_ordinary_account_cannot_change_lifecycle(self):
        for action in (end_engagement, complete_onboarding):
            with self.assertRaises(PermissionDenied):
                action(self.engagement, self.account)
        self.client.force_login(self.account)
        self.assertEqual(self.client.post(self.url, self.data(status='ended')).status_code, 403)
