import json
import logging
import math

from cloudinary.utils import cloudinary_url
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST
from import_export.admin import ImportExportActionModelAdmin

from blog.forms import ArticleForm
from blog.media import adopt_event_gallery_image, upload_editorial_image
from blog.models import (Article, ArticleRevision, Categories, Comments,
                         MediaAsset)
from blog.workflow import (approve_revision, publish_article_directly,
                           request_changes, submit_article)
from events.models import EventGalleryImage, event_image_effectively_public_q
from utils.cloudinary_paths import cloudinary_folder

logger = logging.getLogger(__name__)


def _visible_editorial_assets_q():
    return (
        Q(
            source_event_image__isnull=True,
            public_id__startswith=f'{cloudinary_folder("editorial")}/',
        )
        | (
            Q(public_id__startswith=f'{cloudinary_folder("events")}/')
            & event_image_effectively_public_q('source_event_image__')
        )
    )


def _visible_editorial_assets():
    return MediaAsset.objects.filter(_visible_editorial_assets_q())


def _media_asset_payload(asset, *, can_edit=False):
    warnings = []
    if asset.width < 1200 or asset.height < 675:
        warnings.append('This image is relatively small and may look soft in large placements.')
    if asset.quality_score is not None and asset.quality_score < 0.45:
        warnings.append('This image has a low focus-quality score; review it before publication.')
    return {
        'id': asset.pk,
        'url': asset.transformed_url('inline'),
        'feature_url': asset.feature_url,
        'original_url': asset.secure_url,
        'crop_url': reverse('admin:blog_mediaasset_crop', args=(asset.pk,)),
        'metadata_url': reverse('admin:blog_mediaasset_metadata', args=(asset.pk,)),
        'alt_text': asset.alt_text,
        'caption': asset.caption,
        'width': asset.width,
        'height': asset.height,
        'filename': asset.original_filename,
        'warnings': warnings,
        'can_edit': can_edit,
    }


def _event_gallery_asset_payload(image):
    thumbnail_url, _ = cloudinary_url(
        image.public_id,
        secure=True,
        type='upload',
        width=360,
        height=240,
        crop='fill',
        gravity='auto',
        fetch_format='auto',
        quality='auto',
        dpr='auto',
    )
    return {
        'id': image.pk,
        'url': thumbnail_url,
        'original_url': image.secure_url,
        'alt_text': image.alt_text,
        'width': image.width or 0,
        'height': image.height or 0,
        'filename': image.original_filename or image.public_id.rsplit('/', 1)[-1],
        'event_title': image.event.title,
        'adopt_url': reverse('admin:blog_mediaasset_adopt_event', args=(image.pk,)),
    }


@admin.register(Article)
class ArticleAdmin(ImportExportActionModelAdmin):
    form = ArticleForm
    change_form_template = 'admin/blog/article_change_form.html'
    list_display = (
        'article_title',
        'article_author',
        'workflow_status',
        'is_published',
        'publish_date',
    )
    list_filter = ('workflow_status', 'is_published', 'publish_date', 'date_created', 'article_author')
    search_fields = ('article_title', 'article_content')
    date_hierarchy = 'publish_date'
    ordering = ('workflow_status', '-date_updated')
    actions = ('submit_selected_for_review',)
    readonly_fields = (
        'feature_image_control',
        'review_feedback',
        'article_author',
        'workflow_status',
        'is_published',
        'pending_revision',
        'published_revision',
        'publish_date',
    )
    fieldsets = (
        ('Article essentials', {
            'classes': ('oef-article-essentials',),
            'fields': (
                'article_title',
                'article_excerpt',
                'feature_image_control',
                'feature_media',
                'feature_crop',
                'clear_feature_image',
            ),
            'description': 'Set the headline, summary and lead image readers will see after approval.',
        }),
        ('Write your article', {
            'classes': ('oef-article-writing',),
            'fields': (
                'article_content',
            ),
            'description': (
                'Write the full story here. You can upload, paste or drag approved '
                'inline images into the editor.'
            ),
        }),
        ('Organise and discover', {
            'classes': ('oef-article-taxonomy',),
            'fields': (
                'category',
                'tags',
            ),
            'description': 'Choose up to four sections and add focused search terms for discovery.',
        }),
        ('Review feedback', {
            'classes': ('oef-review-feedback',),
            'fields': ('review_feedback',),
            'description': 'The latest requested changes and earlier editorial notes stay with this article.',
        }),
        ('Editorial workflow', {
            'classes': ('collapse', 'oef-editorial-workflow'),
            'fields': (
                'article_author',
                'workflow_status',
                'pending_revision',
                'published_revision',
                'is_published',
                'publish_date',
            ),
        }),
    )

    class Media:
        css = {'all': ('blog/vendor/cropperjs/cropper-1.6.2.min.css', 'css/article-admin.css')}
        js = (
            'blog/vendor/cropperjs/cropper-1.6.2.min.js',
            'blog/js/editorial-media-manager.js',
            'blog/js/article-feature-media.js',
            'blog/js/article-admin-tags.js',
        )

    def has_import_permission(self, request):
        """Article imports can bypass the editorial workflow, so keep them superuser-only."""
        return request.user.is_superuser

    @admin.display(description='Feature image')
    def feature_image_control(self, obj):
        current_url = ''
        current_id = ''
        current_alt = ''
        current_name = ''
        current_crop = '{}'
        source_label = ''
        featured_img = False
        if obj and obj.feature_media_id:
            current_url = obj.feature_media.cropped_url(obj.feature_crop, 'feature')
            current_id = obj.feature_media_id
            current_alt = obj.feature_media.alt_text
            current_name = obj.feature_media.original_filename
            source_label = 'Managed OEF media'
            featured_img = True
            current_crop = json.dumps(obj.feature_crop or {})
        elif obj and obj.feature_img and str(obj.feature_img) != 'feature_default.jpg':
            try:
                current_url = obj.feature_img.url
                featured_img = True
            except (ValueError, AttributeError):
                current_url = ''
            current_name = str(obj.feature_img)
            source_label = 'Legacy image — replace or remove before review'

        preview = format_html(
            '<img class="oef-feature-image__preview" src="{}" alt="{}"{}>',
            current_url,
            current_alt,
            '' if current_url else ' hidden',
        )
        return format_html(
            '<div class="oef-feature-image" data-current-id="{}" data-current-url="{}" '
            'data-current-alt="{}" data-current-crop="{}" data-library-url="{}" '
            'data-event-library-url="{}" data-upload-url="{}">'
            '{}'
            '<div class="oef-feature-image__details">'
            '<strong class="oef-feature-image__name">{}</strong>'
            '<span class="oef-feature-image__source">{}</span>'
            '<span class="oef-feature-image__empty"{}>No feature image selected.</span>'
            '</div>'
            '<div class="oef-feature-image__actions">'
            '<button type="button" class="button" data-feature-action="library">{}</button>'
            '<button type="button" class="button oef-feature-image__remove" '
            'data-feature-action="remove"{}>Remove</button>'
            '</div>'
            '</div>',
            current_id,
            current_url,
            current_alt,
            current_crop,
            reverse('admin:blog_mediaasset_library'),
            reverse('admin:blog_mediaasset_event_library'),
            reverse('admin:blog_mediaasset_upload'),
            preview,
            current_name,
            source_label,
            ' hidden' if current_url else '',
            'Replace Image' if featured_img else 'Add Image',
            '' if current_url else ' hidden',
        )

    @admin.display(description='Editorial notes')
    def review_feedback(self, obj):
        if not obj or not obj.pk:
            return 'Review feedback will appear here after the first submission.'
        revisions = obj.revisions.exclude(review_notes='').select_related('reviewed_by').order_by('-number')
        if not revisions:
            return 'No review notes have been recorded for this article.'

        items = []
        for revision in revisions:
            reviewer = 'Editorial reviewer'
            if revision.reviewed_by:
                reviewer = revision.reviewed_by.get_full_name() or revision.reviewed_by.username or reviewer
            reviewed_at = (
                date_format(localtime(revision.reviewed_at), 'j M Y, P')
                if revision.reviewed_at
                else 'Not yet reviewed'
            )
            current_class = (
                ' oef-review-history__item--current'
                if revision.status == ArticleRevision.Status.CHANGES_REQUESTED
                and obj.workflow_status == Article.WorkflowStatus.CHANGES_REQUESTED
                else ''
            )
            items.append(format_html(
                '<article class="oef-review-history__item{}">'
                '<div class="oef-review-history__meta">'
                '<strong>Revision {}</strong><span>{}</span><span>{}</span><span>{}</span>'
                '</div><p>{}</p></article>',
                current_class,
                revision.number,
                revision.get_status_display(),
                reviewer,
                reviewed_at,
                revision.review_notes,
            ))
        return format_html(
            '<div class="oef-review-history">{}</div>',
            format_html_join('', '{}', ((item,) for item in items)),
        )

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        has_pending_revision = bool(obj and obj.pending_revision_id)
        context['oef_can_submit'] = (
            request.user.has_perm('blog.submit_article')
            and not has_pending_revision
        )
        context['oef_can_publish_now'] = request.user.is_superuser and not has_pending_revision
        return super().render_change_form(request, context, add, change, form_url, obj)

    def _submit_saved_article(self, request, obj):
        if obj.workflow_status == Article.WorkflowStatus.PUBLISHED:
            self.message_user(
                request,
                'No draft changes were detected, so no duplicate revision was created.',
                level=messages.WARNING,
            )
        else:
            try:
                revision = submit_article(obj, request.user)
            except (PermissionDenied, ValidationError) as exc:
                detail = ' '.join(getattr(exc, 'messages', [])) or 'Permission denied.'
                self.message_user(request, detail, level=messages.ERROR)
            else:
                self.message_user(
                    request,
                    f'Revision {revision.number} was submitted for review.',
                    level=messages.SUCCESS,
                )
        return HttpResponseRedirect(reverse('admin:blog_article_change', args=[obj.pk]))

    def _publish_saved_article(self, request, obj):
        if not request.user.is_superuser:
            self.message_user(
                request,
                'Only a superuser can publish an article directly.',
                level=messages.ERROR,
            )
        elif obj.workflow_status == Article.WorkflowStatus.PUBLISHED:
            self.message_user(
                request,
                'No draft changes were detected, so no duplicate revision was created.',
                level=messages.WARNING,
            )
        else:
            try:
                publish_article_directly(obj, request.user)
            except (PermissionDenied, ValidationError) as exc:
                detail = ' '.join(getattr(exc, 'messages', [])) or 'Permission denied.'
                self.message_user(request, detail, level=messages.ERROR)
            else:
                self.message_user(
                    request,
                    'The article was published directly and recorded in revision history.',
                    level=messages.SUCCESS,
                )
        return HttpResponseRedirect(reverse('admin:blog_article_change', args=[obj.pk]))

    def response_add(self, request, obj, post_url_continue=None):
        if '_publish_now' in request.POST:
            return self._publish_saved_article(request, obj)
        if '_submit_for_review' in request.POST:
            return self._submit_saved_article(request, obj)
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if '_publish_now' in request.POST:
            return self._publish_saved_article(request, obj)
        if '_submit_for_review' in request.POST:
            return self._submit_saved_article(request, obj)
        return super().response_change(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            'article_author', 'feature_media', 'pending_revision', 'published_revision'
        )
        if request.user.is_superuser or request.user.has_perm('blog.review_article'):
            return queryset
        return queryset.filter(article_author=request.user)

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        if not allowed or obj is None:
            return allowed
        if obj.pending_revision_id and not request.user.has_perm('blog.review_article'):
            return False
        return (
            request.user.is_superuser
            or request.user.has_perm('blog.review_article')
            or obj.article_author_id == request.user.pk
        )

    def save_model(self, request, obj, form, change):
        if not obj.article_author_id:
            obj.article_author = request.user
        elif not request.user.has_perm('blog.review_article'):
            obj.article_author = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Submit selected drafts for review')
    def submit_selected_for_review(self, request, queryset):
        submitted = 0
        for article in queryset:
            try:
                submit_article(article, request.user)
                submitted += 1
            except (PermissionDenied, ValidationError) as exc:
                detail = ' '.join(getattr(exc, 'messages', [])) or 'Permission denied.'
                self.message_user(
                    request,
                    f'{article.article_title}: {detail}',
                    level=messages.ERROR,
                )
        if submitted:
            self.message_user(
                request,
                f'{submitted} article revision(s) submitted for review.',
                level=messages.SUCCESS,
            )

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.has_perm('blog.submit_article'):
            actions.pop('submit_selected_for_review', None)
        return actions


@admin.register(ArticleRevision)
class ArticleRevisionAdmin(admin.ModelAdmin):
    change_form_template = 'admin/blog/article_revision_change_form.html'
    list_display = ('article', 'number', 'status', 'created_by', 'submitted_at', 'reviewed_by')
    list_filter = ('status', 'submitted_at', 'reviewed_at')
    search_fields = ('article__article_title', 'title', 'created_by__email')
    actions = ('approve_selected', 'request_changes_selected')
    fields = (
        'article',
        'number',
        'title',
        'excerpt',
        'content',
        'feature_image_url',
        'media_assets',
        'status',
        'created_by',
        'submitted_at',
        'review_notes',
        'reviewed_by',
        'reviewed_at',
        'published_at',
    )

    class Media:
        css = {'all': ('css/article-admin.css',)}

    def get_readonly_fields(self, request, obj=None):
        return tuple(field for field in self.fields if field != 'review_notes')

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        awaiting_review = obj and obj.status == ArticleRevision.Status.IN_REVIEW
        context['oef_can_request_changes'] = (
            awaiting_review and request.user.has_perm('blog.review_article')
        )
        context['oef_can_approve'] = (
            awaiting_review and request.user.has_perm('blog.publish_article')
        )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_change(self, request, obj):
        try:
            if '_request_changes' in request.POST:
                request_changes(obj, request.user, obj.review_notes)
                self.message_user(
                    request,
                    'Changes were requested and the draft was returned to the writer.',
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(reverse('admin:blog_article_change', args=[obj.article_id]))
            if '_approve_revision' in request.POST:
                approve_revision(obj, request.user)
                self.message_user(request, 'The revision was approved and published.', messages.SUCCESS)
                return HttpResponseRedirect(reverse('admin:blog_article_change', args=[obj.article_id]))
        except (PermissionDenied, ValidationError) as exc:
            detail = ' '.join(getattr(exc, 'messages', [])) or 'Permission denied.'
            self.message_user(request, detail, level=messages.ERROR)
            return HttpResponseRedirect(reverse('admin:blog_articlerevision_change', args=[obj.pk]))
        return super().response_change(request, obj)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_perm('blog.review_article')

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('article', 'created_by', 'reviewed_by')
        if request.user.is_superuser or request.user.has_perm('blog.review_article'):
            return queryset
        return queryset.filter(article__article_author=request.user)

    @admin.action(description='Approve and publish selected revisions')
    def approve_selected(self, request, queryset):
        approved = 0
        for revision in queryset:
            try:
                approve_revision(revision, request.user)
                approved += 1
            except (PermissionDenied, ValidationError) as exc:
                detail = ' '.join(getattr(exc, 'messages', [])) or 'Permission denied.'
                self.message_user(request, f'{revision}: {detail}', level=messages.ERROR)
        if approved:
            self.message_user(request, f'{approved} revision(s) published.', messages.SUCCESS)

    @admin.action(description='Request changes on selected revisions')
    def request_changes_selected(self, request, queryset):
        changed = 0
        for revision in queryset:
            try:
                request_changes(revision, request.user, revision.review_notes)
                changed += 1
            except (PermissionDenied, ValidationError) as exc:
                detail = ' '.join(getattr(exc, 'messages', [])) or 'Permission denied.'
                self.message_user(request, f'{revision}: {detail}', level=messages.ERROR)
        if changed:
            self.message_user(request, f'Changes requested on {changed} revision(s).', messages.SUCCESS)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.has_perm('blog.publish_article'):
            actions.pop('approve_selected', None)
        if not request.user.has_perm('blog.review_article'):
            actions.pop('request_changes_selected', None)
        return actions


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = (
        'original_filename',
        'format',
        'dimensions',
        'uploaded_by',
        'approved_for_publication',
        'created_at',
    )
    list_filter = ('format', 'approved_for_publication', 'created_at')
    search_fields = ('original_filename', 'alt_text', 'caption', 'public_id')
    readonly_fields = (
        'asset_id',
        'public_id',
        'secure_url',
        'format',
        'width',
        'height',
        'bytes',
        'uploaded_by',
        'approved_for_publication',
        'created_at',
    )

    @admin.display(description='Dimensions')
    def dimensions(self, obj):
        return f'{obj.width} × {obj.height}'

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(_visible_editorial_assets_q())

    def has_change_permission(self, request, obj=None):
        globally_allowed = super().has_change_permission(request, obj)
        if request.user.is_superuser or request.user.has_perm('blog.approve_mediaasset'):
            return globally_allowed
        return bool(
            obj and obj.uploaded_by_id == request.user.pk
            and request.user.has_perm('blog.view_mediaasset')
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        custom_urls = [
            path(
                'picker/',
                self.admin_site.admin_view(self.picker_view),
                name='blog_mediaasset_picker',
            ),
            path(
                'upload/',
                self.admin_site.admin_view(require_POST(self.upload_view)),
                name='blog_mediaasset_upload',
            ),
            path(
                'library/',
                self.admin_site.admin_view(self.library_view),
                name='blog_mediaasset_library',
            ),
            path(
                'event-library/',
                self.admin_site.admin_view(self.event_library_view),
                name='blog_mediaasset_event_library',
            ),
            path(
                'event-library/<int:object_id>/adopt/',
                self.admin_site.admin_view(require_POST(self.adopt_event_image_view)),
                name='blog_mediaasset_adopt_event',
            ),
            path(
                '<path:object_id>/crop/',
                self.admin_site.admin_view(require_POST(self.crop_view)),
                name='blog_mediaasset_crop',
            ),
            path(
                '<path:object_id>/metadata/',
                self.admin_site.admin_view(require_POST(self.metadata_view)),
                name='blog_mediaasset_metadata',
            ),
        ]
        return custom_urls + super().get_urls()

    def picker_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        return render(request, 'admin/blog/mediaasset/picker.html', {
            **self.admin_site.each_context(request),
            'assets': _visible_editorial_assets().select_related('uploaded_by')[:100],
            'func_num': request.GET.get('CKEditorFuncNum', ''),
            'upload_url': reverse('admin:blog_mediaasset_upload'),
            'title': 'OEF editorial media',
        })

    def upload_view(self, request):
        if not request.user.has_perm('blog.add_mediaasset'):
            raise PermissionDenied
        try:
            asset = upload_editorial_image(
                request.FILES.get('image'),
                request.user,
                request.POST.get('alt_text'),
                request.POST.get('caption'),
            )
        except ValidationError as exc:
            return JsonResponse({'error': ' '.join(exc.messages)}, status=400)
        except Exception:
            logger.exception('Editorial media upload failed.')
            return JsonResponse({'error': 'The image upload service is currently unavailable.'}, status=502)
        return JsonResponse(_media_asset_payload(asset, can_edit=True), status=201)

    def library_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        assets = _visible_editorial_assets().select_related('uploaded_by')[:100]
        return JsonResponse({
            'assets': [
                _media_asset_payload(
                    asset,
                    can_edit=self.has_change_permission(request, asset),
                )
                for asset in assets
            ],
        })

    def event_library_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        images = EventGalleryImage.objects.select_related('event').filter(
            public_id__startswith=f'{cloudinary_folder("events")}/',
        ).filter(
            event_image_effectively_public_q(),
        ).order_by('-created_at', '-pk')
        page = Paginator(
            images,
            settings.OEF_EVENT_MEDIA_LIBRARY_PAGE_SIZE,
        ).get_page(request.GET.get('page'))
        return JsonResponse({
            'assets': [_event_gallery_asset_payload(image) for image in page.object_list],
            'next_url': (
                f'{reverse("admin:blog_mediaasset_event_library")}?page={page.next_page_number()}'
                if page.has_next() else None
            ),
            'total_count': page.paginator.count,
        })

    def adopt_event_image_view(self, request, object_id):
        if not request.user.has_perm('blog.add_mediaasset'):
            raise PermissionDenied
        image = get_object_or_404(
            EventGalleryImage.objects.select_related('event').filter(
                event_image_effectively_public_q(),
            ),
            pk=object_id,
            public_id__startswith=f'{cloudinary_folder("events")}/',
        )
        try:
            asset, _created = adopt_event_gallery_image(image, request.user)
        except ValidationError as exc:
            return JsonResponse({'error': ' '.join(exc.messages)}, status=409)
        return JsonResponse(
            _media_asset_payload(
                asset,
                can_edit=self.has_change_permission(request, asset),
            ),
            status=201 if _created else 200,
        )

    def crop_view(self, request, object_id):
        asset = get_object_or_404(_visible_editorial_assets(), pk=object_id)
        if not self.has_view_permission(request, asset):
            raise PermissionDenied
        usage = request.POST.get('usage', 'inline')
        crop_mode = request.POST.get('crop_mode', 'fixed')
        crop = {
            'x': request.POST.get('x'),
            'y': request.POST.get('y'),
            'width': request.POST.get('width'),
            'height': request.POST.get('height'),
        }
        try:
            source_width = float(request.POST.get('source_width') or asset.width)
            source_height = float(request.POST.get('source_height') or asset.height)
            display_crop = {key: float(value) for key, value in crop.items()}
            if (
                not math.isfinite(source_width)
                or not math.isfinite(source_height)
                or source_width <= 0
                or source_height <= 0
            ):
                raise ValidationError('The crop source dimensions are invalid.')
            original_crop = {
                'x': display_crop['x'] * asset.width / source_width,
                'y': display_crop['y'] * asset.height / source_height,
                'width': display_crop['width'] * asset.width / source_width,
                'height': display_crop['height'] * asset.height / source_height,
            }
            url = asset.cropped_url(original_crop, usage, crop_mode)
            normalised = {
                key: round(value, 2) for key, value in original_crop.items()
            }
        except (TypeError, ValueError, OverflowError):
            return JsonResponse(
                {'error': 'The image crop coordinates are invalid.'}, status=400,
            )
        except ValidationError as exc:
            return JsonResponse({'error': ' '.join(exc.messages)}, status=400)
        return JsonResponse({
            'url': url, 'crop': normalised, 'usage': usage, 'crop_mode': crop_mode,
        })

    def metadata_view(self, request, object_id):
        asset = get_object_or_404(_visible_editorial_assets(), pk=object_id)
        if not self.has_change_permission(request, asset):
            raise PermissionDenied
        alt_text = request.POST.get('alt_text', '').strip()
        caption = request.POST.get('caption', '').strip()
        if not alt_text:
            return JsonResponse({'error': 'Alternative text is required.'}, status=400)
        if len(alt_text) > 255 or len(caption) > 500:
            return JsonResponse({'error': 'The media metadata is too long.'}, status=400)
        asset.alt_text = alt_text
        asset.caption = caption
        asset.save(update_fields=('alt_text', 'caption'))
        return JsonResponse(_media_asset_payload(asset, can_edit=True))


@admin.register(Categories)
class CategoriesAdmin(ImportExportActionModelAdmin):
    list_display = ['title']
    search_fields = ['title']


@admin.register(Comments)
class CommentAdmin(ImportExportActionModelAdmin):
    list_display = ('name', 'body', 'post', 'created_on', 'website', 'active')
    list_filter = ('active', 'created_on')
    search_fields = ('name', 'email', 'body')
    actions = ['approve_comments']

    @admin.action(description='Approve selected comments')
    def approve_comments(self, request, queryset):
        queryset.update(active=True)
