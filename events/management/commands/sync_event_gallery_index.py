from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import EventGalleryImage, Events
from mainsite.services.event_gallery import (gallery_user_tags,
                                             get_admin_gallery_page)
from utils.cloudinary_paths import cloudinary_environment_tag


class Command(BaseCommand):
    help = 'Index environment-matched Cloudinary event images in the gallery table. Dry-run is the default.'

    def add_arguments(self, parser):
        parser.add_argument('--event', type=int, help='Only sync one event primary key.')
        parser.add_argument(
            '--execute', action='store_true',
            help='Write the planned index changes. Without this flag, only report them.',
        )
        parser.add_argument(
            '--require-assets', action='store_true',
            help='Fail when no environment-matched assets are found.',
        )

    def handle(self, *args, **options):
        events = Events.objects.order_by('pk')
        if options.get('event'):
            events = events.filter(pk=options['event'])
        if not events.exists():
            raise CommandError('No matching events were found.')

        created = updated = seen = skipped = 0
        planned_assets = []
        environment_tag = cloudinary_environment_tag()
        publication_tag = settings.CLOUDINARY_GALLERY_PUBLICATION_TAG
        for event in events:
            cursor = None
            event_seen = 0
            while True:
                try:
                    page = get_admin_gallery_page(
                        event, next_cursor=cursor, page_size=500,
                    )
                except Exception as exc:
                    raise CommandError(
                        f'Could not read Cloudinary images for {event}: {exc}'
                    ) from exc
                for asset in page['assets']:
                    if environment_tag not in asset.tags:
                        skipped += 1
                        continue
                    values = {
                        'event': event,
                        'asset_id': asset.asset_id,
                        'secure_url': asset.url,
                        'original_filename': Path(asset.public_id).name[:255],
                        'width': asset.width,
                        'height': asset.height,
                        'alt_text': asset.alt,
                        'tags': gallery_user_tags(event, asset.tags),
                    }
                    existing = EventGalleryImage.objects.filter(
                        public_id=asset.public_id,
                    ).first()
                    was_created = existing is None
                    planned_assets.append((asset, values, existing))
                    created += int(was_created)
                    updated += int(not was_created)
                    seen += 1
                    event_seen += 1
                cursor = page.get('next_cursor')
                if not cursor:
                    break
            self.stdout.write(f'{event}: {event_seen} environment-matched image(s).')

        if options['require_assets'] and not seen:
            raise CommandError('No environment-matched Cloudinary gallery images were found.')

        if options['execute']:
            with transaction.atomic():
                for asset, values, existing in planned_assets:
                    if existing:
                        for field, value in values.items():
                            setattr(existing, field, value)
                        existing.save(update_fields=(*values.keys(), 'updated_at'))
                    else:
                        EventGalleryImage.objects.create(
                            public_id=asset.public_id,
                            is_public=publication_tag in asset.tags,
                            **values,
                        )
        action = 'Indexed' if options['execute'] else 'Would index'
        self.stdout.write(self.style.SUCCESS(
            '{} {} image(s): {} create, {} update; {} other-environment '
            'image(s) skipped.'.format(action, seen, created, updated, skipped)
        ))
