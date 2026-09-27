from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed

from blog.models import ArticleRevision


def protect_revision_snapshot(sender, instance, action, reverse, **kwargs):
    if action not in ('pre_add', 'pre_remove', 'pre_clear'):
        return
    if reverse:
        raise ValidationError('Submitted article revision relations are immutable.')
    if ArticleRevision.objects.filter(pk=instance.pk, snapshot_locked=True).exists():
        raise ValidationError('Submitted article revision relations are immutable.')


for through_model in (
    ArticleRevision.contributors.through,
    ArticleRevision.categories.through,
    ArticleRevision.tags.through,
    ArticleRevision.media_assets.through,
):
    m2m_changed.connect(
        protect_revision_snapshot,
        sender=through_model,
        dispatch_uid=f'protect_article_revision_{through_model._meta.db_table}',
    )
