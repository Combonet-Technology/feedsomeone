import tempfile
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from user.models import TeamMember, UserProfile

from .models import Vacancy, VacancyApplication, VolunteerOffer


@override_settings(CLOUDINARY_STORAGE={})
class SeedRecruitmentDemoTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_directory = tempfile.TemporaryDirectory()
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_directory.name)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        cls.media_directory.cleanup()
        super().tearDownClass()

    @patch(
        'opportunities.management.commands.seed_recruitment_demo.render_offer_pdf',
        return_value=b'%PDF-demo-offer',
    )
    def test_command_creates_all_recruitment_scenarios(self, render_offer_pdf):
        UserProfile.objects.create_superuser(
            email='owner@example.com',
            password='owner-test-password',
        )

        call_command('seed_recruitment_demo', count=26, reset=True)

        applications = VacancyApplication.objects.filter(
            email__endswith='@recruitment-demo.test'
        )
        self.assertEqual(applications.count(), 26)
        self.assertEqual(Vacancy.objects.filter(slug__startswith='demo-').count(), 4)
        offers = VolunteerOffer.objects.filter(application__in=applications)
        self.assertEqual(offers.count(), 14)
        self.assertEqual(offers.exclude(letter_pdf='').count(), 14)
        self.assertEqual(render_offer_pdf.call_count, 14)
        self.assertEqual(TeamMember.objects.filter(source_application__in=applications).count(), 8)
        members = TeamMember.objects.filter(source_application__in=applications)
        for status in ('invited', 'onboarding', 'active', 'inactive'):
            self.assertEqual(members.filter(status=status).count(), 2)
        self.assertEqual(members.filter(user__is_staff=True).count(), 6)
        self.assertEqual(members.filter(user__is_staff=False).count(), 2)
        rejected = applications.filter(status='not_selected')
        self.assertEqual(rejected.count(), 6)
        for status in ('not_sent', 'sent', 'failed'):
            self.assertEqual(rejected.filter(rejection_email_status=status).count(), 2)
        sent_rejections = rejected.filter(rejection_email_status='sent')
        self.assertEqual(sent_rejections.filter(rejection_email_sent_at__isnull=False).count(), 2)
        self.assertEqual(sent_rejections.exclude(rejection_email_message_id='').count(), 2)
        failed_rejections = rejected.filter(rejection_email_status='failed')
        self.assertEqual(failed_rejections.exclude(rejection_email_error='').count(), 2)

    @patch(
        'opportunities.management.commands.seed_recruitment_demo.render_offer_pdf',
        return_value=b'%PDF-demo-offer',
    )
    def test_command_is_idempotent(self, render_offer_pdf):
        call_command('seed_recruitment_demo', count=13, reset=True)
        call_command('seed_recruitment_demo', count=13)

        self.assertEqual(
            VacancyApplication.objects.filter(
                email__endswith='@recruitment-demo.test'
            ).count(),
            13,
        )
        self.assertEqual(render_offer_pdf.call_count, 7)

    @patch(
        'opportunities.management.commands.seed_recruitment_demo.render_offer_pdf',
        return_value=b'%PDF-demo-offer',
    )
    def test_reset_does_not_cascade_to_non_demo_applications(self, render_offer_pdf):
        call_command('seed_recruitment_demo', count=13, reset=True)
        demo_vacancy = Vacancy.objects.get(slug='demo-grant-writer')
        protected_application = VacancyApplication.objects.create(
            vacancy=demo_vacancy,
            full_name='Protected Local Applicant',
            email='protected-local@example.com',
            phone='+2348000000000',
            cv='vacancy_applications/demo/protected-local.pdf',
            cover_letter='Non-demo local record attached to a demo vacancy.',
        )

        call_command('seed_recruitment_demo', count=13, reset=True)

        self.assertTrue(
            VacancyApplication.objects.filter(pk=protected_application.pk).exists()
        )
