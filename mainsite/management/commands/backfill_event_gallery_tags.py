import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cloudinary.uploader
from cloudinary import Search
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from events.models import Events
from mainsite.services.event_gallery import configure_cloudinary
from utils.cloudinary_paths import normalise_cloudinary_segment


def search_resources(expression):
    """Return every Cloudinary image matching a bounded search expression."""
    resources = []
    cursor = None
    while True:
        query = (
            Search().expression(expression).with_field('tags')
            .sort_by('created_at', 'asc').max_results(500)
        )
        if cursor:
            query = query.next_cursor(cursor)
        response = query.execute()
        resources.extend(response.get('resources') or [])
        cursor = response.get('next_cursor')
        if not cursor:
            return resources


class Command(BaseCommand):
    help = (
        'Attach existing Cloudinary gallery images to database Events by adding '
        'the Event gallery tag and the selected OEF environment tag. Dry-run is the default.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute', action='store_true',
            help='Apply missing Cloudinary tags. Without this flag, only report the plan.',
        )
        parser.add_argument(
            '--environment', default=settings.OEF_CLOUDINARY_ENVIRONMENT,
            help='Target OEF environment, for example production or local-test.',
        )
        parser.add_argument(
            '--event', action='append', default=[],
            help='Limit by Event id, slug, title or gallery tag. Repeat for multiple Events.',
        )
        parser.add_argument(
            '--approve-all', action='store_true',
            help='Also add the publication approval tag to every matched asset.',
        )
        parser.add_argument(
            '--report',
            help='Write the before/after plan to this JSON path for audit and rollback.',
        )

    def handle(self, *args, **options):
        if not configure_cloudinary():
            raise CommandError('Cloudinary credentials are incomplete.')

        environment = normalise_cloudinary_segment(options['environment'])
        environment_tag = f'oef-environment-{environment}'
        publication_tag = settings.CLOUDINARY_GALLERY_PUBLICATION_TAG
        events = Events.objects.exclude(gallery_tag='').order_by('pk')
        selectors = [value.strip() for value in options['event'] if value.strip()]
        if selectors:
            query = Q()
            for value in selectors:
                selector = (
                    Q(event_slug=value) | Q(title__iexact=value) | Q(gallery_tag=value)
                )
                if value.isdigit():
                    selector |= Q(pk=int(value))
                query |= selector
            events = events.filter(query).distinct()
        if not events.exists():
            raise CommandError('No matching Events have gallery tags.')

        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'mode': 'execute' if options['execute'] else 'dry-run',
            'environment': environment,
            'environment_tag': environment_tag,
            'publication_tag': publication_tag,
            'approve_all': options['approve_all'],
            'events': [],
        }
        changes_by_tag = defaultdict(list)
        total_assets = 0
        skipped_conflicts = []

        for event in events:
            resources = {
                item['public_id']: item
                for item in search_resources(
                    f'resource_type:image AND tags={event.gallery_tag}'
                )
            }
            if event.gallery_tag in settings.CLOUDINARY_GALLERIES:
                legacy_folder = f'feed-someone/{event.gallery_tag}'
                resources.update({
                    item['public_id']: item
                    for item in search_resources(
                        f'resource_type:image AND folder={legacy_folder}'
                    )
                })

            assets = []
            for public_id, resource in sorted(resources.items()):
                current_tags = set(resource.get('tags') or ())
                conflicting_environment_tags = sorted(
                    tag for tag in current_tags
                    if tag.startswith('oef-environment-') and tag != environment_tag
                )
                if conflicting_environment_tags:
                    skipped_conflicts.append({
                        'public_id': public_id,
                        'environment_tags': conflicting_environment_tags,
                    })
                    continue
                desired_tags = {event.gallery_tag, environment_tag}
                if options['approve_all']:
                    desired_tags.add(publication_tag)
                missing_tags = sorted(desired_tags - current_tags)
                for tag in missing_tags:
                    changes_by_tag[tag].append(public_id)
                assets.append({
                    'public_id': public_id,
                    'before_tags': sorted(current_tags),
                    'missing_tags': missing_tags,
                    'after_tags': sorted(current_tags | desired_tags),
                })

            total_assets += len(assets)
            report['events'].append({
                'event_id': event.pk,
                'event_title': event.title,
                'gallery_tag': event.gallery_tag,
                'asset_count': len(assets),
                'approved_before': sum(
                    publication_tag in asset['before_tags'] for asset in assets
                ),
                'assets': assets,
            })
            self.stdout.write(
                f'{event.title}: {len(assets)} asset(s), '
                f'{sum(bool(asset["missing_tags"]) for asset in assets)} requiring tags.'
            )

        if options['execute']:
            for tag, public_ids in sorted(changes_by_tag.items()):
                for offset in range(0, len(public_ids), 100):
                    cloudinary.uploader.add_tag(
                        tag,
                        public_ids[offset:offset + 100],
                        resource_type='image',
                        type='upload',
                    )

        report['summary'] = {
            'asset_count': total_assets,
            'assets_requiring_changes': len({
                public_id for public_ids in changes_by_tag.values() for public_id in public_ids
            }),
            'tag_operations': {
                tag: len(public_ids) for tag, public_ids in sorted(changes_by_tag.items())
            },
            'skipped_environment_conflicts': skipped_conflicts,
        }
        report_path = options.get('report')
        if report_path:
            path = Path(report_path)
            if not path.is_absolute():
                path = Path(settings.BASE_DIR) / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2), encoding='utf-8')
            self.stdout.write(f'Report: {path}')

        action = 'Applied' if options['execute'] else 'Would apply'
        self.stdout.write(self.style.SUCCESS(
            '{} {} tag operation(s) across {} asset(s); skipped {} asset(s) '
            'belonging to another environment.'.format(
                action,
                sum(len(ids) for ids in changes_by_tag.values()),
                total_assets,
                len(skipped_conflicts),
            )
        ))
