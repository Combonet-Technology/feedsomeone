from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from blog.content import (image_urls, remove_incomplete_figures,
                          validate_article_content)
from blog.media import (editorial_public_id_from_url,
                        editorial_public_ids_from_urls)
from blog.models import Article, ArticleRevision, MediaAsset
from utils.cloudinary_paths import cloudinary_folder


def _require_permission(user, codename):
    if not user.is_active or not user.is_staff or not user.has_perm(codename):
        raise PermissionDenied


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
    referenced_public_ids = editorial_public_ids_from_urls(content_urls)
    referenced_assets = MediaAsset.objects.filter(public_id__in=referenced_public_ids)
    if set(referenced_assets.values_list('public_id', flat=True)) != referenced_public_ids:
        raise ValidationError(
            'Every inline image must be selected from the managed OEF media library.'
        )
    next_number = (
        article.revisions.aggregate(number=Max('number'))['number'] or 0
    ) + 1
    feature_image_url = ''
    if article.feature_media_id:
        if (
            not article.feature_media.public_id.startswith(
                f'{cloudinary_folder("editorial")}/'
            )
            or editorial_public_id_from_url(article.feature_media.secure_url)
            != article.feature_media.public_id
        ):
            raise ValidationError(
                'The feature image must use OEF media from this environment.'
            )
        feature_image_url = article.feature_media.cropped_url(article.feature_crop, 'feature')
    elif article.feature_img and str(article.feature_img) != 'feature_default.jpg':
        raise ValidationError(
            'This draft still uses a legacy feature image. Choose an OEF media image or remove it before review.'
        )

    revision = ArticleRevision.objects.create(
        article=article,
        number=next_number,
        title=article.article_title,
        excerpt=article.article_excerpt or '',
        content=article.article_content,
        feature_image_url=feature_image_url,
        created_by=user,
    )
    if article.feature_media_id:
        referenced_assets = referenced_assets | MediaAsset.objects.filter(pk=article.feature_media_id)
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
