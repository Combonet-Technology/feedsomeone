from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from opportunities.models import Vacancy, VacancyApplication, VolunteerOffer
from opportunities.offers import render_offer_pdf
from user.models import TeamMember, UserProfile

DEMO_DOMAIN = 'recruitment-demo.test'
DEMO_VACANCIES = (
    ('demo-grant-writer', 'Demo Grant and Research Writer', 'Grants and Research'),
    ('demo-project-manager', 'Demo Project Manager', 'Programmes'),
    ('demo-content-writer', 'Demo Content and Research Writer', 'Content'),
    ('demo-graphic-designer', 'Demo Graphic Designer', 'Design'),
)
SCENARIOS = (
    ('received', 'No offer or staff access'),
    ('reviewing', 'Application under review'),
    ('shortlisted', 'Applicant shortlisted'),
    ('offered', 'Offer sent'),
    ('offer_accepted', 'Offer accepted; agreement not yet signed'),
    ('agreement_signed', 'Agreement signed; ready to grant staff access'),
    ('onboarding', 'Access invitation sent'),
    ('onboarding', 'Staff access onboarding'),
    ('active', 'Active staff access'),
    ('active', 'Staff access revoked'),
    ('not_selected', 'Rejection email ready to send'),
    ('not_selected', 'Rejection email already sent'),
    ('not_selected', 'Rejection email failed; ready to retry'),
)
OFFER_SCENARIO_INDEXES = frozenset(range(3, 10))
TEAM_MEMBER_STATUS_BY_SCENARIO = {
    6: 'invited',
    7: 'onboarding',
    8: 'active',
    9: 'inactive',
}
REJECTION_EMAIL_STATUS_BY_SCENARIO = {
    10: 'not_sent',
    11: 'sent',
    12: 'failed',
}


class Command(BaseCommand):
    help = 'Create clearly labelled local recruitment records for admin testing.'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=40)
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing recruitment demo records before reseeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options['count']
        if count < 8 or count > 200:
            raise CommandError('--count must be between 8 and 200.')

        if options['reset']:
            demo_offers = VolunteerOffer.objects.filter(
                application__email__endswith=f'@{DEMO_DOMAIN}'
            )
            for offer in demo_offers.iterator():
                if offer.letter_pdf:
                    offer.letter_pdf.delete(save=False)
            UserProfile.objects.filter(email__endswith=f'@{DEMO_DOMAIN}').delete()
            VacancyApplication.objects.filter(email__endswith=f'@{DEMO_DOMAIN}').delete()
            Vacancy.objects.filter(
                slug__startswith='demo-',
                applications__isnull=True,
            ).delete()

        group = Group.objects.filter(name='Recruitment Manager').first()
        if not group:
            raise CommandError('Run the recruitment permission migration before seeding.')
        owner = UserProfile.objects.filter(is_superuser=True).order_by('date_joined').first()
        now = timezone.now()

        vacancies = []
        for index, (slug, title, team) in enumerate(DEMO_VACANCIES, start=1):
            vacancy, _ = Vacancy.objects.update_or_create(
                slug=slug,
                defaults={
                    'title': title,
                    'team': team,
                    'summary': 'Local demonstration role for recruitment workflow testing.',
                    'description': 'This record is local test data and is not a live vacancy.',
                    'expectations': 'Use only for local administration testing.',
                    'responsibilities': 'Exercise recruitment workflow states.',
                    'benefits': 'Local workflow verification.',
                    'who_we_are_looking_for': 'Demonstration applicant.',
                    'engagement_type': 'volunteer',
                    'work_mode': 'remote',
                    'location': 'Local test environment',
                    'time_commitment': '10 hours per week',
                    'status': 'draft',
                    'positions_available': 1,
                    'display_order': 900 + index,
                    'is_active': False,
                },
            )
            vacancies.append(vacancy)

        for index in range(1, count + 1):
            scenario_index = (index - 1) % len(SCENARIOS)
            status, scenario = SCENARIOS[scenario_index]
            vacancy = vacancies[(index - 1) % len(vacancies)]
            applicant_number = str(index).zfill(3)
            phone_suffix = str(index).zfill(4)
            email = f'applicant-{applicant_number}@{DEMO_DOMAIN}'
            rejection_email_status = REJECTION_EMAIL_STATUS_BY_SCENARIO.get(
                scenario_index,
                'not_sent',
            )
            rejection_batch_key = (
                uuid5(NAMESPACE_URL, f'oef-rejection-demo-{applicant_number}')
                if rejection_email_status in {'sent', 'failed'}
                else None
            )
            application, _ = VacancyApplication.objects.update_or_create(
                vacancy=vacancy,
                email=email,
                defaults={
                    'full_name': f'Demo Applicant {applicant_number}',
                    'phone': f'+23480000{phone_suffix}',
                    'cv': f'vacancy_applications/demo/demo-{applicant_number}.pdf',
                    'cover_letter': f'DEMO DATA: {scenario}.',
                    'status': status,
                    'newsletter_opt_in': False,
                    'rejection_email_status': rejection_email_status,
                    'rejection_email_batch_key': rejection_batch_key,
                    'rejection_email_message_id': (
                        f'demo-rejection-message-{applicant_number}'
                        if rejection_email_status == 'sent'
                        else ''
                    ),
                    'rejection_email_sent_at': (
                        now - timedelta(days=1)
                        if rejection_email_status == 'sent'
                        else None
                    ),
                    'rejection_email_sent_by': (
                        owner if rejection_email_status == 'sent' else None
                    ),
                    'rejection_email_error': (
                        'Demonstration provider failure; safe to retry.'
                        if rejection_email_status == 'failed'
                        else ''
                    ),
                },
            )

            if scenario_index in OFFER_SCENARIO_INDEXES:
                offer, _ = VolunteerOffer.objects.update_or_create(
                    application=application,
                    defaults={
                        'recipient_name': application.full_name,
                        'recipient_email': application.email,
                        'role_title': vacancy.title,
                        'letter_date': timezone.localdate() - timedelta(days=10),
                        'start_date': timezone.localdate(),
                        'initial_period': 'Three months',
                        'weekly_commitment': '10 hours per week',
                        'work_arrangement': 'Remote',
                        'reporting_contact': 'OEF Founder and Trustee',
                        'role_contribution': 'Demonstrate the local recruitment workflow.',
                        'delivery_status': 'sent',
                        'brevo_message_id': f'demo-message-{applicant_number}',
                        'sent_at': now - timedelta(days=scenario_index),
                        'sent_by': owner,
                    },
                )
                if not offer.letter_pdf:
                    offer.letter_pdf.save(
                        f'demo-volunteer-offer-{applicant_number}.pdf',
                        ContentFile(render_offer_pdf(offer)),
                        save=True,
                    )

            if scenario_index in TEAM_MEMBER_STATUS_BY_SCENARIO:
                user, _ = UserProfile.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': 'Demo',
                        'last_name': f'Applicant {applicant_number}',
                        'is_active': True,
                    },
                )
                user.set_unusable_password()
                access_is_current = scenario_index < 9
                user.is_staff = access_is_current
                user.save(update_fields=('password', 'is_staff', 'date_updated'))
                if access_is_current:
                    user.groups.add(group)
                else:
                    user.groups.remove(group)
                if application.applicant_id != user.pk:
                    application.applicant = user
                    application.save(update_fields=('applicant', 'updated_at'))

                member_status = TEAM_MEMBER_STATUS_BY_SCENARIO[scenario_index]
                TeamMember.objects.update_or_create(
                    user=user,
                    defaults={
                        'source_application': application,
                        'role_title': vacancy.title,
                        'engagement_type': 'volunteer',
                        'status': member_status,
                        'start_date': timezone.localdate(),
                        'activated_at': now if scenario_index in {7, 8} else None,
                        'access_granted_at': now - timedelta(days=5),
                        'access_granted_by': owner,
                        'access_revoked_at': now if scenario_index == 9 else None,
                        'access_revoked_by': owner if scenario_index == 9 else None,
                        'invitation_sent_at': now - timedelta(days=4),
                        'invitation_message_id': f'demo-access-{applicant_number}',
                        'invitation_error': '',
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded {count} local recruitment applications across '
                f'{len(SCENARIOS)} workflow scenarios.'
            )
        )
        self.stdout.write(f'Demo email domain: @{DEMO_DOMAIN}')
