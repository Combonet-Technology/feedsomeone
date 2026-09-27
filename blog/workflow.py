import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from blog.content import (image_urls, remove_incomplete_figures,
                          validate_article_content)
from blog.media import (managed_media_public_id_from_url,
                        managed_media_public_ids_from_urls)
from blog.models import (Article, ArticlePublicationEvent, ArticleRevision,
                         MediaAsset)
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


def _draft_fingerprint(article):
    payload = {
        'title': article.article_title,
        'slug': article.article_slug,
        'excerpt': article.article_excerpt or '',
        'content': article.article_content,
        'feature_media_id': article.feature_media_id,
        'feature_crop': article.feature_crop or {},
        'categories': sorted(article.category.values_list('pk', flat=True)),
        'tags': sorted(article.tags.values_list('pk', flat=True)),
        'author_id': article.article_author_id,
        'contributors': sorted(article.draft_contributors.values_list('pk', flat=True)),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _require_current_draft(article, revision):
    if revision.fingerprint and _draft_fingerprint(article) != revision.fingerprint:
        raise ValidationError('The working draft changed after submission. Submit a new revision.')


def _record_publication(article, revision, actor, action):
    ArticlePublicationEvent.objects.create(
        article=article, revision=revision, actor=actor, action=action,
    )


def _lock_revision(revision):
    article_id = ArticleRevision.objects.values_list('article_id', flat=True).get(pk=revision.pk)
    article = Article.objects.select_for_update().get(pk=article_id)
    return article, ArticleRevision.objects.select_for_update().get(pk=revision.pk)


@transaction.atomic
def submit_article(article, user):
    _require_permission(user, 'blog.submit_article')
    return _create_revision(article, user)


def can_publish_without_review(user):
    return user.is_active and user.is_staff and user.has_perm('blog.publish_without_review')


def _create_revision(article, user, *, direct_bypass=False):
    # Internal helper: both entry points check permission and open a transaction.
    article = Article.objects.select_for_update().get(pk=article.pk)

    if not direct_bypass and article.article_author_id != user.pk and not user.has_perm('blog.review_article'):
        raise PermissionDenied
    if article.pending_revision_id:
        previous = ArticleRevision.objects.select_for_update().get(pk=article.pending_revision_id)
        if not direct_bypass and (
            not previous.fingerprint or _draft_fingerprint(article) == previous.fingerprint
        ):
            raise ValidationError('This article already has a revision awaiting review.')
        previous.status = ArticleRevision.Status.SUPERSEDED
        previous.save(update_fields=('status',))
        article.pending_revision = None
        article.workflow_status = Article.WorkflowStatus.DRAFT
        article.save(update_fields=('pending_revision', 'workflow_status', 'date_updated'))

    article.article_content = remove_incomplete_figures(article.article_content)
    article.full_clean(exclude=('pending_revision', 'published_revision'))
    validate_article_content(article.article_content)
    content_urls = image_urls(article.article_content)
    referenced_public_ids = managed_media_public_ids_from_urls(content_urls)
    next_iteration = (
        article.revisions.aggregate(iteration=Max('iteration'))['iteration'] or 0
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
        iteration=next_iteration,
        title=article.article_title,
        slug=article.article_slug,
        excerpt=article.article_excerpt or '',
        content=article.article_content,
        feature_image_url=feature_image_url,
        feature_crop=article.feature_crop,
        fingerprint=_draft_fingerprint(article),
        created_by=user,
        authored_by=article.article_author,
        snapshot_locked=False,
        direct_bypass=direct_bypass,
    )
    revision.media_assets.set(referenced_assets)
    revision.categories.set(article.category.all())
    revision.tags.set(article.tags.all())
    revision.contributors.set(article.draft_contributors.all())
    revision.snapshot_locked = True
    revision.save(update_fields=('snapshot_locked',))

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
    if (
        revision.created_by_id == reviewer.pk
        or revision.authored_by_id == reviewer.pk
        or revision.contributors.filter(pk=reviewer.pk).exists()
    ):
        raise ValidationError('A contributor cannot review their own article revision.')
    if revision.status != ArticleRevision.Status.IN_REVIEW:
        raise ValidationError('Only revisions awaiting review can be reviewed.')


@transaction.atomic
def approve_revision(revision, reviewer):
    article, revision = _lock_revision(revision)
    _validate_reviewer(revision, reviewer, 'blog.review_article')
    if article.pending_revision_id != revision.pk:
        raise ValidationError('This is no longer the article revision awaiting review.')
    _require_current_draft(article, revision)
    _lock_and_validate_assets(set(
        revision.media_assets.values_list('public_id', flat=True)
    ))

    now = timezone.now()
    revision.status = ArticleRevision.Status.APPROVED
    revision.reviewed_by = reviewer
    revision.reviewed_at = now
    revision.save(update_fields=('status', 'reviewed_by', 'reviewed_at'))
    article.workflow_status = Article.WorkflowStatus.APPROVED
    article.save(update_fields=('workflow_status', 'date_updated'))
    return article


@transaction.atomic
def publish_approved_revision(revision, publisher):
    article, revision = _lock_revision(revision)
    _require_permission(publisher, (
        'blog.publish_without_review' if revision.direct_bypass else 'blog.publish_article'
    ))
    if revision.status != ArticleRevision.Status.APPROVED or article.pending_revision_id != revision.pk:
        raise ValidationError('Only the current approved revision can be published.')
    if revision.direct_bypass is False and not revision.reviewed_by_id:
        raise ValidationError('An independent review is required before publication.')
    _require_current_draft(article, revision)
    _lock_and_validate_assets(set(revision.media_assets.values_list('public_id', flat=True)))
    first_publication = article.published_revision_id is None
    if article.published_revision_id and article.published_revision_id != revision.pk:
        ArticleRevision.objects.filter(pk=article.published_revision_id).update(
            status=ArticleRevision.Status.SUPERSEDED,
        )
    now = timezone.now()
    revision.status = ArticleRevision.Status.PUBLISHED
    revision.published_at = now
    revision.published_by = publisher
    revision.save(update_fields=('status', 'published_at', 'published_by'))
    revision.media_assets.update(approved_for_publication=True)
    article.published_revision = revision
    article.pending_revision = None
    article.workflow_status = Article.WorkflowStatus.PUBLISHED
    article.is_published = True
    if first_publication:
        article.publish_date = now
    article.publication_updated_at = now
    article.save(update_fields=(
        'published_revision', 'pending_revision', 'workflow_status',
        'is_published', 'publish_date', 'publication_updated_at', 'date_updated',
    ))
    _record_publication(
        article, revision, publisher,
        'direct_publish' if revision.direct_bypass else 'publish',
    )
    return article


@transaction.atomic
def return_approved_revision_for_changes(revision, publisher, notes):
    _require_permission(publisher, 'blog.publish_article')
    notes = (notes or '').strip()
    if not notes:
        raise ValidationError('Review notes are required when returning an approved revision.')
    article, revision = _lock_revision(revision)
    if revision.status != ArticleRevision.Status.APPROVED or article.pending_revision_id != revision.pk:
        raise ValidationError('Only the current approved revision can be returned for changes.')
    revision.status = ArticleRevision.Status.CHANGES_REQUESTED
    revision.review_notes = notes
    revision.save(update_fields=('status', 'review_notes'))
    article.pending_revision = None
    article.workflow_status = Article.WorkflowStatus.CHANGES_REQUESTED
    article.save(update_fields=('pending_revision', 'workflow_status', 'date_updated'))
    return article


@transaction.atomic
def unpublish_article(article, publisher):
    _require_permission(publisher, 'blog.publish_article')
    article = Article.objects.select_for_update().get(pk=article.pk)
    if not article.is_published or not article.published_revision_id:
        raise ValidationError('Only a published article can be unpublished.')
    article.is_published = False
    article.workflow_status = Article.WorkflowStatus.UNPUBLISHED
    article.save(update_fields=('is_published', 'workflow_status', 'date_updated'))
    _record_publication(article, article.published_revision, publisher, 'unpublish')
    return article


@transaction.atomic
def republish_article(article, publisher):
    _require_permission(publisher, 'blog.publish_article')
    article = Article.objects.select_for_update().get(pk=article.pk)
    if article.is_published or not article.published_revision_id:
        raise ValidationError('Only an unpublished approved snapshot can be republished.')
    if article.published_revision.legacy_metadata_unverified:
        raise ValidationError('This legacy publication needs a new reviewed revision before republishing.')
    if article.workflow_status == Article.WorkflowStatus.DRAFT or article.pending_revision_id:
        raise ValidationError('This article has an unreviewed draft. Submit and review it first.')
    _require_current_draft(article, article.published_revision)
    article.is_published = True
    article.workflow_status = Article.WorkflowStatus.PUBLISHED
    article.publication_updated_at = timezone.now()
    article.save(update_fields=(
        'is_published', 'workflow_status', 'publication_updated_at', 'date_updated',
    ))
    _record_publication(article, article.published_revision, publisher, 'republish')
    return article


@transaction.atomic
def publish_article_directly(article, publisher, *, revision=None):
    """Publish the current working copy in one step while preserving revision history."""
    _require_permission(publisher, 'blog.publish_without_review')
    article = Article.objects.select_for_update().get(pk=article.pk)
    if article.workflow_status not in (
        Article.WorkflowStatus.DRAFT, Article.WorkflowStatus.IN_REVIEW,
        Article.WorkflowStatus.CHANGES_REQUESTED,
    ):
        raise ValidationError('Use normal publication or republication for this article.')
    if revision is not None:
        revision = ArticleRevision.objects.select_for_update().get(pk=revision.pk)
        if article.pending_revision_id != revision.pk:
            raise ValidationError('This is no longer the current article revision.')
        if revision.status != ArticleRevision.Status.IN_REVIEW:
            raise ValidationError('Only a revision awaiting review can bypass review.')
        _require_current_draft(article, revision)
    if article.is_published and article.published_revision_id and not article.pending_revision_id:
        if article.published_revision.fingerprint == _draft_fingerprint(article):
            raise ValidationError('This article is already published without draft changes.')
    pending = None
    if article.pending_revision_id:
        pending = ArticleRevision.objects.select_for_update().get(pk=article.pending_revision_id)
        if pending.status != ArticleRevision.Status.IN_REVIEW:
            raise ValidationError('Only a revision awaiting review can bypass review.')
        _require_current_draft(article, pending)
    if pending and pending.fingerprint and pending.status == ArticleRevision.Status.IN_REVIEW:
        revision = pending
        # Content remains immutable; the separate publication decision is audited.
        ArticleRevision.objects.filter(pk=revision.pk).update(direct_bypass=True)
        revision.direct_bypass = True
    else:
        revision = _create_revision(article, publisher, direct_bypass=True)
    revision.status = ArticleRevision.Status.APPROVED
    revision.save(update_fields=('status',))
    return publish_approved_revision(revision, publisher)


@transaction.atomic
def request_changes(revision, reviewer, notes):
    notes = (notes or '').strip()
    if not notes:
        raise ValidationError('Review notes are required when requesting changes.')

    article, revision = _lock_revision(revision)
    _validate_reviewer(revision, reviewer, 'blog.review_article')
    if article.pending_revision_id != revision.pk:
        raise ValidationError('This is no longer the article revision awaiting review.')
    _require_current_draft(article, revision)

    revision.status = ArticleRevision.Status.CHANGES_REQUESTED
    revision.reviewed_by = reviewer
    revision.reviewed_at = timezone.now()
    revision.review_notes = notes
    revision.save(update_fields=('status', 'reviewed_by', 'reviewed_at', 'review_notes'))

    article.pending_revision = None
    article.workflow_status = Article.WorkflowStatus.CHANGES_REQUESTED
    article.save(update_fields=('pending_revision', 'workflow_status', 'date_updated'))
    return article
