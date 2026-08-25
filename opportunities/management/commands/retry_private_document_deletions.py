from django.core.management.base import BaseCommand

from opportunities.document_cleanup import process_private_document_deletion
from opportunities.models import PrivateDocumentDeletion


class Command(BaseCommand):
    help = 'Retry pending private-document deletions.'

    def handle(self, *args, **options):
        pending = PrivateDocumentDeletion.objects.filter(
            status=PrivateDocumentDeletion.Status.PENDING,
        ).values_list('pk', flat=True)
        completed = sum(bool(process_private_document_deletion(pk)) for pk in pending)
        self.stdout.write(self.style.SUCCESS(f'Completed {completed} pending deletion(s).'))
