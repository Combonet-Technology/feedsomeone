from django.core.management.base import BaseCommand
from django.utils import timezone

from opportunities.models import Vacancy

VACANCIES = (
    {
        'slug': 'volunteer-content-writer',
        'title': 'Volunteer Content Writer',
        'summary': (
            'Help OEF turn programme updates, research and community stories '
            'into clear, responsible public content.'
        ),
        'description': (
            'OEF is building a small volunteer editorial team to improve how we '
            'document our work, explain humanitarian issues and communicate with '
            'supporters, partners and communities.\n\n'
            'This is a remote, part-time volunteer core-team role. Writers will '
            'work with OEF leadership and programme contributors on articles, '
            'briefings, website copy and impact stories.'
        ),
        'who_we_are_looking_for': (
            'A thoughtful writer or emerging communications professional who can '
            'research carefully, write in clear English and handle stories about '
            'vulnerable people with dignity. NGO experience is useful but not '
            'required. Strong students and early-career applicants are welcome.'
        ),
        'responsibilities': (
            '- Draft and edit articles, programme updates and campaign copy.\n'
            '- Research assigned social-impact topics using reliable sources.\n'
            '- Interview or collect notes from team members when needed.\n'
            '- Follow OEF editorial, safeguarding and evidence standards.\n'
            '- Collaborate through shared documents and respond to editorial feedback.'
        ),
        'expectations': (
            'Commit approximately 4 to 6 hours each week, communicate reliably, '
            'meet agreed deadlines and attend occasional remote planning sessions. '
            'Applicants should be comfortable using Google Docs and willing to '
            'learn responsible AI-assisted writing workflows.'
        ),
        'benefits': (
            '- Practical experience working with a growing Nigerian nonprofit.\n'
            '- Published work and portfolio-building opportunities where appropriate.\n'
            '- Editorial feedback, collaboration and professional references based on contribution.\n'
            '- Exposure to selected AI and productivity tools that support the work.\n'
            '- The opportunity to contribute to communication that supports real community impact.'
        ),
        'status': 'open',
        'positions_available': 5,
    },
    {
        'slug': 'volunteer-graphic-designer',
        'title': 'Volunteer Graphic Designer',
        'summary': (
            'Create clear, respectful visual communication for OEF programmes, '
            'campaigns and public updates.'
        ),
        'description': (
            'This volunteer core-team role supports OEF with social media graphics, '
            'campaign materials and visual assets that communicate our work clearly.'
        ),
        'who_we_are_looking_for': (
            'A dependable designer with a strong eye for hierarchy, accessibility '
            'and respectful nonprofit storytelling.'
        ),
        'responsibilities': (
            '- Design digital campaign and programme materials.\n'
            '- Maintain consistent use of OEF brand assets.\n'
            '- Prepare correctly sized assets for web and social channels.'
        ),
        'expectations': (
            'Communicate reliably, work from agreed briefs and deliver editable '
            'source files with final exports.'
        ),
        'benefits': (
            'Nonprofit portfolio experience, collaborative feedback and the '
            'opportunity to support community-focused communication.'
        ),
        'status': 'filled',
        'positions_available': 1,
    },
    {
        'slug': 'volunteer-project-manager',
        'title': 'Volunteer Project Manager',
        'summary': (
            'Coordinate priorities, timelines and contributors across OEF core-team projects.'
        ),
        'description': (
            'This role helps OEF turn plans into organised, accountable delivery '
            'across content, programmes and operational projects.'
        ),
        'who_we_are_looking_for': (
            'An organised collaborator who can structure work, follow up respectfully '
            'and keep distributed contributors aligned.'
        ),
        'responsibilities': (
            '- Maintain project plans, owners and timelines.\n'
            '- Coordinate remote check-ins and action items.\n'
            '- Surface blockers and support clear handoffs.'
        ),
        'expectations': (
            'Strong written communication, reliable follow-through and comfort '
            'working with shared planning tools.'
        ),
        'benefits': (
            'Hands-on nonprofit project experience, leadership exposure and the '
            'opportunity to improve how a growing foundation operates.'
        ),
        'status': 'filled',
        'positions_available': 1,
    },
)


class Command(BaseCommand):
    help = 'Create or update the initial public OEF core-team vacancies.'

    def handle(self, *args, **options):
        for vacancy_data in VACANCIES:
            slug = vacancy_data['slug']
            defaults = {
                **vacancy_data,
                'is_active': True,
                'published_at': timezone.now(),
            }
            defaults.pop('slug')
            vacancy, created = Vacancy.objects.update_or_create(
                slug=slug,
                defaults=defaults,
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(
                self.style.SUCCESS(f'{action}: {vacancy.title} ({vacancy.status})')
            )
