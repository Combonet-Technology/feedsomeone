import math
import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django_prose_editor.fields import ProseEditorField
from taggit.managers import TaggableManager

from blog.editor import ARTICLE_EDITOR_EXTENSIONS
from user.models import UserProfile


class Categories(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated at")
    title = models.CharField(max_length=255, verbose_name="Title", default='UNCATEGORIZED')

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['title']

    def __str__(self):
        return self.title


class PublishedManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(
            is_published=True,
            is_deleted=False,
        ).select_related('published_revision', 'article_author').order_by('-publish_date')


class Article(models.Model):
    class WorkflowStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        IN_REVIEW = 'in_review', 'In review'
        CHANGES_REQUESTED = 'changes_requested', 'Changes requested'
        PUBLISHED = 'published', 'Published'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    article_title = models.CharField(max_length=100, null=False, blank=False)
    article_excerpt = models.CharField(max_length=255, null=True, blank=True)
    article_slug = models.SlugField(null=False, unique=True, max_length=150)
    article_content = ProseEditorField(
        extensions=ARTICLE_EDITOR_EXTENSIONS,
        sanitize=True,
    )
    feature_img = models.ImageField(
        upload_to='article_feature_img',
        blank=True,
        help_text='Legacy local feature image. New editorial images use managed OEF media.',
    )
    feature_media = models.ForeignKey(
        'MediaAsset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='featured_articles',
    )
    feature_crop = models.JSONField(
        default=dict,
        blank=True,
        help_text='Original-image crop coordinates for the 16:9 feature placement.',
    )
    article_author = models.ForeignKey(UserProfile,
                                       on_delete=models.CASCADE,
                                       null=True,
                                       blank=True,
                                       related_name="user_article")
    category = models.ManyToManyField(Categories, blank=True, verbose_name="Category", related_name="article")
    is_published = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    workflow_status = models.CharField(
        max_length=24,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.DRAFT,
    )
    pending_revision = models.ForeignKey(
        'ArticleRevision',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='+',
    )
    published_revision = models.ForeignKey(
        'ArticleRevision',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name='published_articles',
    )
    publish_date = models.DateTimeField(default=timezone.now)
    date_created = models.DateTimeField(auto_now_add=True, verbose_name="Created_at")
    date_updated = models.DateTimeField(auto_now=True, verbose_name="Updated_at")

    published = PublishedManager()
    objects = models.Manager()
    tags = TaggableManager()

    class Meta:
        default_manager_name = 'objects'
        base_manager_name = 'objects'
        permissions = (
            ('submit_article', 'Can submit articles for editorial review'),
            ('review_article', 'Can review article revisions'),
            ('publish_article', 'Can publish approved article revisions'),
        )

    def __str__(self):
        return self.article_title

    @property
    def public_title(self):
        return self.published_revision.title if self.published_revision_id else self.article_title

    @property
    def public_excerpt(self):
        return self.published_revision.excerpt if self.published_revision_id else self.article_excerpt

    @property
    def public_content(self):
        return self.published_revision.content if self.published_revision_id else self.article_content

    @property
    def public_feature_image_url(self):
        if self.published_revision_id and self.published_revision.feature_image_url:
            return self.published_revision.feature_image_url
        if self.feature_media_id:
            return self.feature_media.cropped_url(self.feature_crop, 'feature')
        try:
            if self.feature_img and self.feature_img.name == 'feature_default.jpg':
                return ''
            return self.feature_img.url if self.feature_img else ''
        except (ValueError, AttributeError):
            return ''

    @property
    def public_modified_at(self):
        if self.published_revision_id:
            return self.published_revision.published_at or self.published_revision.created_at
        return self.date_updated

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).only(
                'article_title',
                'article_excerpt',
                'article_content',
                'feature_img',
                'feature_media',
                'feature_crop',
                'workflow_status',
            ).first()
            if original and original.workflow_status == self.WorkflowStatus.PUBLISHED:
                draft_changed = any((
                    original.article_title != self.article_title,
                    original.article_excerpt != self.article_excerpt,
                    original.article_content != self.article_content,
                    str(original.feature_img) != str(self.feature_img),
                    original.feature_media_id != self.feature_media_id,
                    original.feature_crop != self.feature_crop,
                ))
                if draft_changed:
                    self.workflow_status = self.WorkflowStatus.DRAFT
                    self.pending_revision = None
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('article:article_detail',
                       args=[self.publish_date.year,
                             self.publish_date.month,
                             self.publish_date.day,
                             self.article_slug])

    def to_dict(self):
        return {
            'uuid': str(self.uuid),
            # 'article_title': self.article_title,
            'article_slug': self.article_slug,
            # 'article_content': self.article_content,
            'feature_img': self.public_feature_image_url or None,
            'article_author': self.article_author.get_full_name() if self.article_author else None,
            'category': [category.title for category in self.category.all()],
            'is_published': self.is_published,
            'is_deleted': self.is_deleted,
            # 'publish_date': self.publish_date.isoformat(),
            # 'date_created': self.date_created.isoformat(),
            # 'date_updated': self.date_updated.isoformat(),
            'tags': list(self.tags.names()),
        }


#     override save method to autogenerate slug

class Comments(models.Model):
    post = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=80)
    email = models.EmailField()
    body = models.TextField()
    website = models.CharField(max_length=100, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_on']

    def __str__(self):
        return f'Comment {self.body} by {self.name}'


class InnerComments(models.Model):
    post = models.ForeignKey(Comments, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=80)
    email = models.EmailField()
    body = models.TextField()
    # website = models.CharField(max_length=100)
    created_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    def __str__(self):
        return f'reply {self.body} to {self.post}'


class MediaAsset(models.Model):
    source_event_image = models.OneToOneField(
        'events.EventGalleryImage',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='editorial_media_asset',
        help_text='Event-gallery source retained while this image is available to articles.',
    )
    asset_id = models.CharField(max_length=255, unique=True)
    public_id = models.CharField(max_length=500, unique=True)
    secure_url = models.URLField(max_length=1000, unique=True)
    original_filename = models.CharField(max_length=255)
    format = models.CharField(max_length=20)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    bytes = models.PositiveBigIntegerField()
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=500, blank=True)
    quality_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        editable=False,
        help_text='Cloudinary focus-quality score when available.',
    )
    uploaded_by = models.ForeignKey(
        UserProfile,
        on_delete=models.PROTECT,
        related_name='editorial_media_uploads',
    )
    approved_for_publication = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        permissions = (
            ('approve_mediaasset', 'Can approve editorial media for publication'),
        )

    def __str__(self):
        return self.original_filename

    def transformed_url(self, preset='inline'):
        from cloudinary.utils import cloudinary_url

        presets = {
            'feature': dict(width=1600, height=900, crop='fill', gravity='auto'),
            'inline': dict(width=1400, height=1400, crop='limit'),
            'landscape': dict(width=1200, height=675, crop='fill', gravity='auto'),
            'square': dict(width=900, height=900, crop='fill', gravity='auto'),
            'portrait': dict(width=900, height=1200, crop='fill', gravity='auto'),
        }
        options = presets.get(preset, presets['inline'])
        url, _ = cloudinary_url(
            self.public_id, secure=True, type='upload', fetch_format='auto',
            quality='auto', dpr='auto', **options,
        )
        return url

    def cropped_url(self, crop_data, preset='inline', crop_mode='fixed'):
        from cloudinary.utils import cloudinary_url

        targets = {'feature': (1600, 900), 'inline': (1600, 900)}
        if preset not in targets:
            raise ValidationError('The requested image placement is invalid.')
        if crop_mode not in ('fixed', 'flexible'):
            raise ValidationError('The requested crop mode is invalid.')
        if preset == 'feature' and crop_mode != 'fixed':
            raise ValidationError('Feature images must use the fixed 16:9 crop.')
        if not crop_data:
            return self.transformed_url('feature' if preset == 'feature' else 'inline')
        try:
            coordinates = tuple(
                float(crop_data[key]) for key in ('x', 'y', 'width', 'height')
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValidationError('The image crop coordinates are invalid.')
        if not all(math.isfinite(value) for value in coordinates):
            raise ValidationError('The image crop coordinates are invalid.')
        x, y, width, height = (round(value) for value in coordinates)
        if (
            x < 0 or y < 0 or width < 1 or height < 1
            or x + width > self.width + 1 or y + height > self.height + 1
        ):
            raise ValidationError('The image crop falls outside the original image.')
        target_width, target_height = targets[preset]
        ratio = width / height
        if crop_mode == 'fixed' and abs(ratio - (16 / 9)) > 0.03:
            raise ValidationError('The fixed crop must use the required 16:9 aspect ratio.')
        if crop_mode == 'flexible' and not 0.75 <= ratio <= 2.4:
            raise ValidationError('Flexible inline crops must stay between 3:4 and 12:5.')
        delivery = (
            {'width': target_width, 'height': target_height, 'crop': 'fill'}
            if crop_mode == 'fixed'
            else {'width': 1400, 'height': 1600, 'crop': 'limit'}
        )
        url, _ = cloudinary_url(
            self.public_id,
            secure=True,
            type='upload',
            fetch_format='auto',
            quality='auto',
            dpr='auto',
            transformation=[
                {'x': x, 'y': y, 'width': width, 'height': height, 'crop': 'crop'},
                delivery,
            ],
        )
        return url

    @property
    def feature_url(self):
        return self.transformed_url('feature')


class ArticleRevision(models.Model):
    class Status(models.TextChoices):
        IN_REVIEW = 'in_review', 'In review'
        APPROVED = 'approved', 'Approved'
        CHANGES_REQUESTED = 'changes_requested', 'Changes requested'
        SUPERSEDED = 'superseded', 'Superseded'

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='revisions',
    )
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=100)
    excerpt = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    feature_image_url = models.URLField(max_length=1000, blank=True)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.IN_REVIEW,
    )
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name='article_revisions_created',
    )
    reviewed_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='article_revisions_reviewed',
    )
    review_notes = models.TextField(blank=True)
    media_assets = models.ManyToManyField(MediaAsset, blank=True, related_name='article_revisions')
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('article', 'number'),
                name='unique_article_revision_number',
            ),
        ]

    def __str__(self):
        return f'{self.article.article_title} - revision {self.number}'

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            immutable_fields = (
                'article_id', 'number', 'title', 'excerpt', 'content',
                'feature_image_url', 'created_by_id',
            )
            if original and any(getattr(original, field) != getattr(self, field) for field in immutable_fields):
                raise ValidationError('Submitted article revision content is immutable.')
        super().save(*args, **kwargs)
