from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from blog.content import (image_urls, remove_incomplete_figures,
                          validate_article_content)
from blog.media import (managed_media_public_id_from_url,
                        managed_media_public_ids_from_urls)
from blog.models import Article, ArticleRevision, MediaAsset
from events.models import (EventGalleryImage, Events,
                           event_image_effectively_public_q)
from utils.cloudinary_paths import cloudinary_folder


def _require_permission(user, codename):
    if not user.is_active or not user.is_staff or not user.has_perm(codename):
        raise PermissionDenied


def _lock_and_validate_assets(public_ids):
    public_ids = set(public_ids)
    asset_refs = list(MediaAsset.objects.filter(
        public_id__in=public_ids,
    ).values('public_id', 'source_event_image_id'))
    source_event_ids = [
        asset['source_event_image_id'] for asset in asset_refs
        if asset['source_event_image_id']
    ]
    event_ids = list(EventGalleryImage.objects.filter(
        pk__in=source_event_ids,
    ).values_list('event_id', flat=True))
    list(Events.objects.select_for_update().filter(pk__in=event_ids))
    event_sources = EventGalleryImage.objects.select_for_update().filter(
        pk__in=source_event_ids,
    )
    if event_sources.exclude(event_image_effectively_public_q()).exists():
        raise ValidationError(
            'An event image used by this article or its parent gallery is now private. '
            'Remove or replace it before continuing.'
        )
    assets = list(MediaAsset.objects.select_for_update().filter(
        public_id__in=public_ids,
    ))
    if {asset.public_id for asset in assets} != set(public_ids):
        raise ValidationError(
            'Every image must be selected from the managed OEF media library.'
        )
    event_prefix = f'{cloudinary_folder("events")}/'
    editorial_prefix = f'{cloudinary_folder("editorial")}/'
    if any(
        (
            asset.public_id.startswith(event_prefix)
            and not asset.source_event_image_id
        )
        or (
            asset.public_id.startswith(editorial_prefix)
            and asset.source_event_image_id
        )
        for asset in assets
    ):
        raise ValidationError(
            'Event media must have a valid gallery source, and editorial uploads '
            'cannot use event-gallery provenance.'
        )
    return assets


@transaction.atomic
def submit_article(article, user):
    _require_permission(user, 'blog.submit_article')
    article = Article.objects.select_for_update().get(pk=article.pk)

    if article.article_author_id != user.pk and not user.has_perm('blog.review_article'):
        raise PermissionDenied
    if article.pending_revision_id:
        raise ValidationError('This article already has a revision awaiting review.')

    article.article_content = remove_incomplete_figures(article.article_content)
    article.full_clean(exclude=('pending_revision', 'published_revision'))
    validate_article_content(article.article_content)
    content_urls = image_urls(article.article_content)
    referenced_public_ids = managed_media_public_ids_from_urls(content_urls)
    next_number = (
        article.revisions.aggregate(number=Max('number'))['number'] or 0
    ) + 1
    feature_image_url = ''
    if article.feature_media_id:
        if (
            not article.feature_media.public_id.startswith((
                f'{cloudinary_folder("editorial")}/',
                f'{cloudinary_folder("events")}/',
            ))
            or managed_media_public_id_from_url(article.feature_media.secure_url)
            != article.feature_media.public_id
        ):
            raise ValidationError(
                'The feature image must use OEF media from this environment.'
            )
        referenced_public_ids.add(article.feature_media.public_id)
        feature_image_url = article.feature_media.cropped_url(article.feature_crop, 'feature')
    elif article.feature_img and str(article.feature_img) != 'feature_default.jpg':
        raise ValidationError(
            'This draft still uses a legacy feature image. Choose an OEF media image or remove it before review.'
        )
    referenced_assets = _lock_and_validate_assets(referenced_public_ids)

    revision = ArticleRevision.objects.create(
        article=article,
        number=next_number,
        title=article.article_title,
        excerpt=article.article_excerpt or '',
        content=article.article_content,
        feature_image_url=feature_image_url,
        created_by=user,
    )
    revision.media_assets.set(referenced_assets)

    article.pending_revision = revision
    article.workflow_status = Article.WorkflowStatus.IN_REVIEW
    article.save(update_fields=(
        'article_content',
        'pending_revision',
        'workflow_status',
        'date_updated',
    ))
    return revision


def _validate_reviewer(revision, reviewer, permission):
    _require_permission(reviewer, permission)
    if revision.created_by_id == reviewer.pk and not reviewer.is_superuser:
        raise ValidationError('A reviewer cannot approve or reject their own revision.')
    if revision.status != ArticleRevision.Status.IN_REVIEW:
        raise ValidationError('Only revisions awaiting review can be reviewed.')


@transaction.atomic
def approve_revision(revision, reviewer):
    revision = ArticleRevision.objects.select_for_update().select_related('article').get(pk=revision.pk)
    article = Article.objects.select_for_update().get(pk=revision.article_id)
    _validate_reviewer(revision, reviewer, 'blog.publish_article')
    if article.pending_revision_id != revision.pk:
        raise ValidationError('This is no longer the article revision awaiting review.')
    _lock_and_validate_assets(set(
        revision.media_assets.values_list('public_id', flat=True)
    ))

    now = timezone.now()
    if article.published_revision_id:
        ArticleRevision.objects.filter(
            pk=article.published_revision_id,
            status=ArticleRevision.Status.APPROVED,
        ).update(status=ArticleRevision.Status.SUPERSEDED)

    revision.status = ArticleRevision.Status.APPROVED
    revision.reviewed_by = reviewer
    revision.reviewed_at = now
    revision.published_at = now
    revision.save(update_fields=('status', 'reviewed_by', 'reviewed_at', 'published_at'))
    revision.media_assets.update(approved_for_publication=True)

    was_published = article.is_published
    article.published_revision = revision
    article.pending_revision = None
    article.workflow_status = Article.WorkflowStatus.PUBLISHED
    article.is_published = True
    if not was_published:
        article.publish_date = now
    article.save(update_fields=(
        'published_revision',
        'pending_revision',
        'workflow_status',
        'is_published',
        'publish_date',
        'date_updated',
    ))
    return article


@transaction.atomic
def publish_article_directly(article, publisher):
    """Publish the current working copy in one step while preserving revision history."""
    if not publisher.is_active or not publisher.is_staff or not publisher.is_superuser:
        raise PermissionDenied
    revision = submit_article(article, publisher)
    return approve_revision(revision, publisher)


@transaction.atomic
def request_changes(revision, reviewer, notes):
    notes = (notes or '').strip()
    if not notes:
        raise ValidationError('Review notes are required when requesting changes.')

    revision = ArticleRevision.objects.select_for_update().select_related('article').get(pk=revision.pk)
    article = Article.objects.select_for_update().get(pk=revision.article_id)
    _validate_reviewer(revision, reviewer, 'blog.review_article')
    if article.pending_revision_id != revision.pk:
        raise ValidationError('This is no longer the article revision awaiting review.')

    revision.status = ArticleRevision.Status.CHANGES_REQUESTED
    revision.reviewed_by = reviewer
    revision.reviewed_at = timezone.now()
    revision.review_notes = notes
    revision.save(update_fields=('status', 'reviewed_by', 'reviewed_at', 'review_notes'))

    article.pending_revision = None
    article.workflow_status = Article.WorkflowStatus.CHANGES_REQUESTED
    article.save(update_fields=('pending_revision', 'workflow_status', 'date_updated'))
    return article
