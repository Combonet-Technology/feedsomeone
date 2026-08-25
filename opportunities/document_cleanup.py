import logging

from django.db import transaction
from django.utils import timezone

from opportunities.models import PrivateDocumentDeletion
from opportunities.storage import VacancyPrivateDocumentStorage

logger = logging.getLogger(__name__)


def enqueue_private_document_deletion(storage_name):
    if not storage_name:
        return None
    task, _ = PrivateDocumentDeletion.objects.get_or_create(storage_name=str(storage_name))
    transaction.on_commit(lambda: process_private_document_deletion(task.pk))
    return task


def process_private_document_deletion(task_id):
    task = PrivateDocumentDeletion.objects.filter(pk=task_id).first()
    if not task or task.status == PrivateDocumentDeletion.Status.COMPLETED:
        return True
    task.attempts += 1
    try:
        VacancyPrivateDocumentStorage().delete(task.storage_name)
    except Exception as exc:
        task.last_error = str(exc)[:2000]
        task.save(update_fields=('attempts', 'last_error'))
        logger.exception('Private document cleanup failed for task %s.', task.pk)
        return False
    task.status = PrivateDocumentDeletion.Status.COMPLETED
    task.completed_at = timezone.now()
    task.last_error = ''
    task.save(update_fields=('status', 'completed_at', 'attempts', 'last_error'))
    return True
