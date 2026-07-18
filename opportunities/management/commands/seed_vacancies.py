import os
import re
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from opportunities.models import Vacancy

DEFAULT_SOURCE = Path(settings.BASE_DIR, 'local-data', 'oef_vacancies.md')
YAML_BLOCK = re.compile(r'```ya?ml\s+(.*?)```', re.DOTALL | re.IGNORECASE)
REQUIRED_FIELDS = {
    'slug',
    'title',
    'team',
    'summary',
    'description',
    'who_we_are_looking_for',
    'responsibilities',
    'expectations',
    'benefits',
    'time_commitment',
    'status',
    'positions_available',
    'display_order',
}
IMPORTABLE_FIELDS = {
    field.name
    for field in Vacancy._meta.fields
    if field.name
    not in {
        'id',
        'created_at',
        'updated_at',
        'published_at',
        'catalogue_version',
    }
}


def load_catalogue(source):
    try:
        markdown = source.read_text(encoding='utf-8')
    except FileNotFoundError as exc:
        raise CommandError(f'Vacancy catalogue not found: {source}') from exc

    match = YAML_BLOCK.search(markdown)
    if not match:
        raise CommandError('The vacancy catalogue must contain one fenced YAML block.')

    try:
        payload = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise CommandError(f'Invalid vacancy catalogue YAML: {exc}') from exc

    if not isinstance(payload, dict):
        raise CommandError('The vacancy catalogue YAML must be a mapping.')

    version = payload.get('catalogue_version')
    defaults = payload.get('defaults', {})
    vacancies = payload.get('vacancies')
    if not isinstance(version, int) or version < 1:
        raise CommandError('catalogue_version must be a positive integer.')
    if not isinstance(defaults, dict):
        raise CommandError('defaults must be a mapping.')
    if not isinstance(vacancies, list) or not vacancies:
        raise CommandError('vacancies must be a non-empty list.')

    slugs = set()
    display_orders = set()
    normalized = []
    for index, vacancy in enumerate(vacancies, start=1):
        if not isinstance(vacancy, dict):
            raise CommandError(f'Vacancy {index} must be a mapping.')

        merged = {**defaults, **vacancy}
        missing = sorted(REQUIRED_FIELDS - merged.keys())
        if missing:
            raise CommandError(
                f'Vacancy {index} is missing required fields: {", ".join(missing)}.'
            )

        unknown = sorted(merged.keys() - IMPORTABLE_FIELDS - {'slug'})
        if unknown:
            raise CommandError(
                f'Vacancy {index} has unsupported fields: {", ".join(unknown)}.'
            )

        slug = str(merged['slug']).strip()
        if not slug or slug in slugs:
            raise CommandError(f'Vacancy {index} has a blank or duplicate slug.')
        slugs.add(slug)

        display_order = merged['display_order']
        if not isinstance(display_order, int) or display_order < 1:
            raise CommandError(
                f'Vacancy {slug} must have a positive integer display_order.'
            )
        if display_order in display_orders:
            raise CommandError(f'display_order {display_order} is duplicated.')
        display_orders.add(display_order)

        merged['slug'] = slug
        merged['catalogue_version'] = version
        normalized.append(merged)

    return normalized


class Command(BaseCommand):
    help = 'Import OEF vacancies from an explicitly supplied Markdown catalogue.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            default=os.getenv('VACANCY_CATALOGUE_PATH', str(DEFAULT_SOURCE)),
            help='Path to a Markdown file containing one fenced YAML catalogue.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Reapply catalogue content even when the stored version is current.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate and simulate the import, then roll back all database writes.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source = Path(options['source']).expanduser().resolve()
        vacancies = load_catalogue(source)
        self.stdout.write(f'Catalogue: {source}')

        counts = {'created': 0, 'updated': 0, 'unchanged': 0}
        for vacancy_data in vacancies:
            slug = vacancy_data['slug']
            defaults = {
                **vacancy_data,
                'published_at': timezone.now(),
            }
            defaults.pop('slug')
            vacancy, created = Vacancy.objects.get_or_create(
                slug=slug,
                defaults=defaults,
            )
            action = 'created'
            if not created and (
                options['force']
                or vacancy.catalogue_version < defaults['catalogue_version']
            ):
                published_at = vacancy.published_at or defaults.pop('published_at')
                for field, value in defaults.items():
                    setattr(vacancy, field, value)
                vacancy.published_at = published_at
                vacancy.save()
                action = 'updated'
            elif not created:
                action = 'unchanged'

            counts[action] += 1
            self.stdout.write(
                f'{action.title()}: {vacancy.title} ({vacancy.status})'
            )

        if options['dry_run']:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('Dry run complete; changes rolled back.'))

        self.stdout.write(
            self.style.SUCCESS(
                'Summary: '
                f'{counts["created"]} created, '
                f'{counts["updated"]} updated, '
                f'{counts["unchanged"]} unchanged.'
            )
        )
