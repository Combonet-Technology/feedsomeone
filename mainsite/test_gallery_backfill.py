import json
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import call, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from events.models import Events


@override_settings(
    OEF_CLOUDINARY_ENVIRONMENT='local-test',
    CLOUDINARY_GALLERY_PUBLICATION_TAG='publication-approved',
    CLOUDINARY_GALLERIES={'feed-someone-1.0': {'tag': 'feed-someone-1.0'}},
)
class EventGalleryBackfillCommandTests(TestCase):
    def setUp(self):
        self.event = Events.objects.create(
            title='Feed Someone 1.0', event_date=date(2019, 12, 27),
            event_slug='feed-someone-1-0', gallery_tag='feed-someone-1.0',
            gallery_is_public=True, location='Akure',
            feature_img='event_feature_img/test.jpg', time='10:00', content='Event.',
        )

    @patch('mainsite.management.commands.backfill_event_gallery_tags.configure_cloudinary', return_value=True)
    @patch('mainsite.management.commands.backfill_event_gallery_tags.search_resources')
    @patch('mainsite.management.commands.backfill_event_gallery_tags.cloudinary.uploader.add_tag')
    def test_dry_run_reports_without_mutating_cloudinary(self, add_tag, search, configure):
        search.side_effect = [
            [{'public_id': 'legacy/photo-1', 'tags': ['feed-someone-1.0', 'publication-approved']}],
            [{'public_id': 'legacy/photo-1', 'tags': ['feed-someone-1.0', 'publication-approved']}],
        ]
        output = StringIO()

        call_command(
            'backfill_event_gallery_tags', '--environment', 'production',
            stdout=output,
        )

        add_tag.assert_not_called()
        self.assertIn('Would apply 1 tag operation(s) across 1 asset(s);', output.getvalue())

    @patch('mainsite.management.commands.backfill_event_gallery_tags.configure_cloudinary', return_value=True)
    @patch('mainsite.management.commands.backfill_event_gallery_tags.search_resources')
    @patch('mainsite.management.commands.backfill_event_gallery_tags.cloudinary.uploader.add_tag')
    def test_execute_adds_mapping_tags_without_changing_approval(self, add_tag, search, configure):
        search.side_effect = [
            [
                {'public_id': 'legacy/photo-1', 'tags': ['feed-someone-1.0', 'publication-approved']},
                {'public_id': 'legacy/photo-2', 'tags': []},
            ],
            [
                {'public_id': 'legacy/photo-1', 'tags': ['feed-someone-1.0', 'publication-approved']},
                {'public_id': 'legacy/photo-2', 'tags': []},
            ],
        ]
        with TemporaryDirectory() as directory:
            report_path = f'{directory}/report.json'
            call_command(
                'backfill_event_gallery_tags', '--execute', '--environment', 'production',
                '--report', report_path,
            )
            report = json.loads(Path(report_path).read_text(encoding='utf-8'))

        self.assertEqual(add_tag.call_args_list, [
            call('feed-someone-1.0', ['legacy/photo-2'], resource_type='image', type='upload'),
            call(
                'oef-environment-production',
                ['legacy/photo-1', 'legacy/photo-2'],
                resource_type='image', type='upload',
            ),
        ])
        self.assertEqual(report['events'][0]['approved_before'], 1)
        self.assertNotIn(
            'publication-approved',
            report['events'][0]['assets'][1]['after_tags'],
        )

    @patch('mainsite.management.commands.backfill_event_gallery_tags.configure_cloudinary', return_value=True)
    @patch('mainsite.management.commands.backfill_event_gallery_tags.search_resources')
    @patch('mainsite.management.commands.backfill_event_gallery_tags.cloudinary.uploader.add_tag')
    def test_skips_cross_environment_assets(self, add_tag, search, configure):
        search.side_effect = [
            [{'public_id': 'local/photo', 'tags': ['feed-someone-1.0', 'oef-environment-local']}],
            [],
        ]

        output = StringIO()
        call_command(
            'backfill_event_gallery_tags', '--execute', '--environment', 'production',
            stdout=output,
        )

        add_tag.assert_not_called()
        self.assertIn('skipped 1 asset(s) belonging to another environment', output.getvalue())
