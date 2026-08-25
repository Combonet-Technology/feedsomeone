from django.db.models.signals import post_delete
from django.dispatch import receiver

from opportunities.document_cleanup import enqueue_private_document_deletion
from opportunities.models import VacancyApplication, VolunteerOffer


@receiver(post_delete, sender=VacancyApplication)
def delete_application_cv(sender, instance, **kwargs):
    if instance.cv and instance.cv.name:
        enqueue_private_document_deletion(instance.cv.name)


@receiver(post_delete, sender=VolunteerOffer)
def delete_offer_pdf(sender, instance, **kwargs):
    if instance.letter_pdf and instance.letter_pdf.name:
        enqueue_private_document_deletion(instance.letter_pdf.name)
