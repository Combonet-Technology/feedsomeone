import logging
import mimetypes
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.db import transaction
from django.http import FileResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_POST
from import_export.admin import ImportExportActionModelAdmin

from blog.media import (event_image_ids_with_editorial_usage,
                        validate_editorial_image,
                        validate_event_images_can_be_made_private)
from blog.models import MediaAsset
from events.forms import EventGalleryImageAdminForm, EventsAdminForm
from events.models import (EventGalleryImage, Events, GalleryUploadBatch,
                           GalleryUploadItem,
                           is_event_image_effectively_public)
from mainsite.services.event_gallery import (add_publication_tag,
                                             delete_event_images,
                                             gallery_user_tags,
                                             remove_publication_tag,
                                             update_event_image_metadata,
                                             upload_event_image)

logger = logging.getLogger(__name__)


def _log_gallery_action(request, action, *, image_ids=(), event_ids=(), count=0):
    """Write operator activity to internal logs without exposing it in UI copy."""
    actor_id = getattr(getattr(request, 'user', None), 'pk', None)
    occurred_at = timezone.now().isoformat()
    image_ids = sorted(image_ids)
    event_ids = sorted(event_ids)
    logger.info(
        'Gallery action completed action=%s actor_id=%s count=%s '
        'image_ids=%s event_ids=%s occurred_at=%s',
        action, actor_id, count, image_ids, event_ids, occurred_at,
        extra={
            'gallery_action': action,
            'gallery_actor_id': actor_id,
            'gallery_image_ids': image_ids,
            'gallery_event_ids': event_ids,
            'gallery_affected_count': count,
            'gallery_occurred_at': occurred_at,
        },
    )


@admin.register(Events)
class EventsAdmin(ImportExportActionModelAdmin):
    form = EventsAdminForm
    list_display = ('title', 'event_date', 'location', 'gallery_status', 'manage_gallery_link')
    list_filter = ('gallery_is_public', 'event_date')
    search_fields = ('title', 'description', 'location', 'gallery_tag')
    readonly_fields = ('gallery_tag', 'manage_gallery_link')
    fieldsets = (
        (None, {'fields': ('title', 'event_date', 'time', 'location', 'feature_img')}),
        ('Event details', {'fields': ('description', 'content', 'budget', 'max_volunteer_needed', 'event_slug')}),
        ('Evidence gallery', {
            'fields': ('gallery_tag', 'gallery_is_public', 'manage_gallery_link'),
            'description': 'Manage the images associated with this event.',
        }),
        ('Ownership', {'fields': ('event_author',), 'classes': ('collapse',)}),
    )

    @admin.display(description='Gallery', boolean=True)
    def gallery_status(self, obj):
        return obj.gallery_is_public

    @admin.display(description='Event images')
    def manage_gallery_link(self, obj):
        if not obj or not obj.pk:
            return 'Save the event before adding images.'
        url = reverse('admin:events_eventgalleryimage_upload')
        return format_html('<a class="button" href="{}?event={}">Add images</a>', url, obj.pk)

    def get_urls(self):
        custom = [
            path(
                '<path:object_id>/gallery/', self.admin_site.admin_view(self.gallery_view),
                name='events_events_gallery',
            ),
        ]
        return custom + super().get_urls()

    def get_actions(self, request):
        """Prevent bulk deletion from hiding gallery cleanup requirements."""
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        event = self.get_object(request, object_id)
        if (
            event is not None
            and self.has_delete_permission(request, event)
            and event.gallery_images.exists()
        ):
            self.message_user(
                request,
                'This event cannot be deleted while gallery images remain. '
                'Delete its images through Gallery images, then delete the event.',
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse('admin:events_events_change', args=(event.pk,))
            )
        return super().delete_view(request, object_id, extra_context)

    def _event_for_gallery(self, request, object_id):
        event = get_object_or_404(Events, pk=object_id)
        if not self.has_change_permission(request, event):
            raise PermissionDenied
        return event

    def gallery_view(self, request, object_id):
        event = self._event_for_gallery(request, object_id)
        url = reverse('admin:events_eventgalleryimage_changelist')
        return HttpResponseRedirect(f'{url}?event__id__exact={event.pk}')

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            original = (
                Events.objects.select_for_update().get(pk=obj.pk)
                if change else None
            )
            if original and original.gallery_is_public and not obj.gallery_is_public:
                images = list(
                    EventGalleryImage.objects.select_for_update()
                    .filter(event=original, is_public=True)
                )
                validate_event_images_can_be_made_private(images)
            super().save_model(request, obj, form, change)


@admin.register(EventGalleryImage)
class EventGalleryImageAdmin(admin.ModelAdmin):
    """Compact database-backed management surface for Cloudinary images."""

    form = EventGalleryImageAdminForm
    change_list_template = 'admin/events/eventgalleryimage/change_list.html'
    list_display = (
        'filename', 'event', 'alt_text', 'tag_summary', 'is_public',
        'deletion_status', 'created_at',
    )
    list_display_links = ('filename',)
    list_filter = ('event', 'is_public', 'deletion_status', 'created_at')
    list_editable = ('alt_text', 'is_public')
    search_fields = ('original_filename', 'public_id', 'alt_text', 'event__title')
    ordering = ('-created_at', '-pk')
    actions = (
        'mark_selected_images_public', 'mark_selected_images_private',
        'delete_selected_gallery_images',
    )
    readonly_fields = (
        'asset_id', 'public_id', 'secure_url_link', 'original_filename',
        'dimensions', 'uploaded_by', 'created_at', 'updated_at',
        'deletion_status', 'deletion_error', 'deletion_requested_at',
    )
    fieldsets = (
        ('Image record', {'fields': ('event', 'original_filename', 'secure_url_link', 'dimensions')}),
        ('Accessibility and organisation', {'fields': ('alt_text', 'tags_text', 'is_public')}),
        ('Storage reference', {'fields': ('asset_id', 'public_id'), 'classes': ('collapse',)}),
        ('Deletion recovery', {
            'fields': ('deletion_status', 'deletion_requested_at', 'deletion_error'),
            'classes': ('collapse',),
        }),
        ('Audit', {'fields': ('uploaded_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def get_urls(self):
        custom = [
            path('upload/', self.admin_site.admin_view(self.upload_view), name='events_eventgalleryimage_upload'),
            path(
                'stage/', self.admin_site.admin_view(require_POST(self.stage_view)),
                name='events_eventgalleryimage_stage',
            ),
            path(
                'stage/<uuid:batch_id>/<int:item_id>/preview/',
                self.admin_site.admin_view(self.preview_view),
                name='events_eventgalleryimage_preview',
            ),
            path(
                'stage/remove/', self.admin_site.admin_view(require_POST(self.remove_staged_view)),
                name='events_eventgalleryimage_remove_staged',
            ),
            path(
                'stage/cancel/', self.admin_site.admin_view(require_POST(self.cancel_batch_view)),
                name='events_eventgalleryimage_cancel_batch',
            ),
            path(
                'stage/commit/', self.admin_site.admin_view(require_POST(self.commit_view)),
                name='events_eventgalleryimage_commit',
            ),
        ]
        return custom + super().get_urls()

    def has_add_permission(self, request):
        return self.has_change_permission(request)

    def get_readonly_fields(self, request, obj=None):
        readonly = super().get_readonly_fields(request, obj)
        if obj:
            return (*readonly, 'event')
        return readonly

    def add_view(self, request, form_url='', extra_context=None):
        return HttpResponseRedirect(reverse('admin:events_eventgalleryimage_upload'))

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            **(extra_context or {}),
            'gallery_upload_url': reverse('admin:events_eventgalleryimage_upload'),
            'title': 'Gallery images',
        }
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description='Image')
    def filename(self, obj):
        return obj.original_filename or Path(obj.public_id).name

    @admin.display(description='Tags')
    def tag_summary(self, obj):
        return ', '.join(obj.tags or []) or '—'

    @admin.display(description='Image')
    def secure_url_link(self, obj):
        if not obj.secure_url:
            return '—'
        return format_html('<a href="{}" target="_blank" rel="noopener">Open image</a>', obj.secure_url)

    @admin.display(description='Dimensions')
    def dimensions(self, obj):
        if obj.width and obj.height:
            return f'{obj.width} × {obj.height} px'
        return '—'

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def has_delete_permission(self, request, obj=None):
        """Force provider-backed deletion through the recoverable admin action."""
        return obj is None and super().has_delete_permission(request, obj)

    @admin.action(description='Mark selected images as public')
    def mark_selected_images_public(self, request, queryset):
        selected_ids = list(queryset.values_list('pk', flat=True))
        event_ids = set()
        tagged_public_ids = set()
        published = 0
        not_updated_count = 0
        try:
            with transaction.atomic():
                event_ids = set(EventGalleryImage.objects.filter(
                    pk__in=selected_ids,
                ).values_list('event_id', flat=True))
                list(Events.objects.select_for_update().filter(pk__in=event_ids))
                private_images = list(
                    EventGalleryImage.objects.select_for_update().filter(
                        pk__in=selected_ids,
                        is_public=False,
                        deletion_status=EventGalleryImage.DeletionStatus.ACTIVE,
                    )
                )
                if not private_images:
                    self.message_user(request, 'The selected images are already public.')
                    return

                image_ids = [image.pk for image in private_images]
                public_ids = [image.public_id for image in private_images]
                # Treat every requested ID as potentially tagged if the provider
                # call raises after Cloudinary accepted the request.
                tagged_public_ids = set(public_ids)
                add_publication_tag(public_ids)
                EventGalleryImage.objects.filter(
                    pk__in=image_ids,
                    is_public=False,
                    deletion_status=EventGalleryImage.DeletionStatus.ACTIVE,
                ).update(is_public=True)
                updated_public_ids = set(EventGalleryImage.objects.filter(
                    pk__in=image_ids,
                    is_public=True,
                    deletion_status=EventGalleryImage.DeletionStatus.ACTIVE,
                ).values_list('public_id', flat=True))
                not_updated = tagged_public_ids - updated_public_ids
                if not_updated:
                    remove_publication_tag(sorted(not_updated))
                    tagged_public_ids -= not_updated
                    not_updated_count = len(not_updated)
                published = len(updated_public_ids)
        except Exception:
            if tagged_public_ids:
                try:
                    remove_publication_tag(sorted(tagged_public_ids))
                except Exception:
                    logger.exception(
                        'Could not compensate Cloudinary publication tags after publication failed.',
                        extra={
                            'gallery_operation_phase': 'publication_compensation',
                            'gallery_selected_image_ids': selected_ids,
                            'gallery_event_ids': sorted(event_ids),
                            'gallery_actor_id': getattr(request.user, 'pk', None),
                        },
                    )
            logger.exception(
                'Gallery image bulk publication failed.',
                extra={
                    'gallery_operation_phase': 'publication',
                    'gallery_selected_image_ids': selected_ids,
                    'gallery_event_ids': sorted(event_ids),
                    'gallery_actor_id': getattr(request.user, 'pk', None),
                },
            )
            self.message_user(
                request,
                'The selected images could not be made public, and the publication '
                'change was rolled back. Please try again. If the problem continues, '
                'contact an administrator.',
                level=messages.ERROR,
            )
            return
        if published:
            self.message_user(request, f'{published} image(s) marked public.')
            _log_gallery_action(
                request, 'images_marked_public',
                image_ids=selected_ids, event_ids=event_ids, count=published,
            )
        if not_updated_count:
            self.message_user(
                request,
                f'{not_updated_count} image(s) changed while publication was in progress; '
                'they remain private.',
                level=messages.WARNING,
            )

    @admin.action(description='Mark selected images as private')
    def mark_selected_images_private(self, request, queryset):
        selected_ids = []
        event_ids = set()
        public_ids = []
        provider_changed = False
        try:
            with transaction.atomic():
                selected_ids = list(queryset.values_list('pk', flat=True))
                event_ids = set(EventGalleryImage.objects.filter(
                    pk__in=selected_ids,
                ).values_list('event_id', flat=True))
                list(Events.objects.select_for_update().filter(pk__in=event_ids))
                public_images = list(
                    EventGalleryImage.objects.select_for_update()
                    .select_related('event')
                    .filter(
                        pk__in=selected_ids,
                        is_public=True,
                        deletion_status=EventGalleryImage.DeletionStatus.ACTIVE,
                    )
                )
                if not public_images:
                    self.message_user(request, 'The selected images are already private.')
                    return
                validate_event_images_can_be_made_private(public_images)
                public_ids = [image.public_id for image in public_images]
                remove_publication_tag(public_ids)
                provider_changed = True
                unpublished = EventGalleryImage.objects.filter(
                    pk__in=[image.pk for image in public_images],
                ).update(is_public=False)
        except ValidationError as exc:
            self.message_user(
                request, ' '.join(exc.messages),
                level=messages.ERROR,
            )
            return
        except Exception:
            if provider_changed:
                try:
                    add_publication_tag(public_ids)
                except Exception:
                    logger.exception(
                        'Could not restore Cloudinary publication tags after a database failure.'
                    )
            logger.exception(
                'Gallery image bulk privacy action failed.',
                extra={
                    'gallery_operation_phase': 'privacy',
                    'gallery_selected_image_ids': selected_ids,
                    'gallery_event_ids': sorted(event_ids),
                    'gallery_actor_id': getattr(request.user, 'pk', None),
                },
            )
            self.message_user(
                request,
                'The selected images could not be made private. Please try again. '
                'If the problem continues, contact an administrator.',
                level=messages.ERROR,
            )
            return
        if unpublished:
            self.message_user(request, f'{unpublished} image(s) marked private.')
            _log_gallery_action(
                request, 'images_marked_private',
                image_ids=selected_ids, event_ids=event_ids, count=unpublished,
            )

    @admin.action(
        description='Delete selected images',
        permissions=('delete',),
    )
    def delete_selected_gallery_images(self, request, queryset):
        if not self.has_delete_permission(request):
            raise PermissionDenied
        selected_ids = list(queryset.values_list('pk', flat=True))
        protected_ids = set()
        pending_images = []
        provider_deleted_ids = set()
        in_progress_ids = set()
        event_ids = set()

        # Persist intent before calling Cloudinary. A retry can safely resume from
        # either PENDING or PROVIDER_DELETED after a worker/process interruption.
        try:
            with transaction.atomic():
                event_ids = set(EventGalleryImage.objects.filter(
                    pk__in=selected_ids,
                ).values_list('event_id', flat=True))
                list(Events.objects.select_for_update().filter(pk__in=event_ids))
                images = list(
                    EventGalleryImage.objects.select_for_update()
                    .filter(pk__in=selected_ids)
                )
                image_ids = [image.pk for image in images]
                # Lock optional adoption rows separately. Joining the nullable
                # reverse one-to-one relation makes PostgreSQL reject FOR UPDATE
                # because the nullable side of an outer join cannot be locked.
                list(MediaAsset.objects.select_for_update().filter(
                    source_event_image_id__in=image_ids,
                ))
                protected_ids = event_image_ids_with_editorial_usage(
                    image_ids
                )
                candidates = [
                    image for image in images if image.pk not in protected_ids
                ]
                provider_deleted_ids = {
                    image.pk for image in candidates
                    if image.deletion_status
                    == EventGalleryImage.DeletionStatus.PROVIDER_DELETED
                }
                retry_before = timezone.now() - timedelta(minutes=10)
                in_progress_ids = {
                    image.pk for image in candidates
                    if (
                        image.deletion_status == EventGalleryImage.DeletionStatus.PENDING
                        and image.deletion_requested_at
                        and image.deletion_requested_at > retry_before
                    )
                }
                pending_images = [
                    image for image in candidates
                    if (
                        image.pk not in provider_deleted_ids
                        and image.pk not in in_progress_ids
                    )
                ]
                if pending_images:
                    EventGalleryImage.objects.filter(
                        pk__in=[image.pk for image in pending_images],
                    ).update(
                        deletion_status=EventGalleryImage.DeletionStatus.PENDING,
                        deletion_error='',
                        deletion_requested_at=timezone.now(),
                    )
        except Exception:
            logger.exception(
                'Gallery image deletion failed during staging.',
                extra={
                    'gallery_operation_phase': 'staging',
                    'gallery_selected_image_ids': selected_ids,
                    'gallery_event_ids': sorted(event_ids),
                    'gallery_actor_id': getattr(request.user, 'pk', None),
                },
            )
            self.message_user(
                request,
                'The deletion request could not be started, and no images were deleted. '
                'Please try again. If the problem continues, contact an administrator.',
                level=messages.ERROR,
            )
            return

        deleted_public_ids = set()
        failed = {}
        if pending_images:
            try:
                deleted_public_ids, failed = delete_event_images(
                    [image.public_id for image in pending_images]
                )
            except Exception:
                logger.exception(
                    'Cloudinary gallery image deletion request failed.',
                    extra={
                        'gallery_operation_phase': 'provider_deletion',
                        'gallery_selected_image_ids': selected_ids,
                        'gallery_pending_image_ids': [image.pk for image in pending_images],
                        'gallery_actor_id': getattr(request.user, 'pk', None),
                    },
                )
                failed = {
                    image.public_id: 'Cloudinary deletion failed; see server logs.'
                    for image in pending_images
                }
            if failed:
                logger.error(
                    'Cloudinary did not delete one or more gallery images: %r',
                    failed,
                    extra={
                        'gallery_operation_phase': 'provider_response',
                        'gallery_selected_image_ids': selected_ids,
                        'gallery_actor_id': getattr(request.user, 'pk', None),
                    },
                )
            public_to_id = {image.public_id: image.pk for image in pending_images}
            provider_deleted_ids.update(
                public_to_id[public_id]
                for public_id in deleted_public_ids
                if public_id in public_to_id
            )
            try:
                with transaction.atomic():
                    if deleted_public_ids:
                        EventGalleryImage.objects.filter(
                            pk__in=provider_deleted_ids,
                        ).update(
                            deletion_status=EventGalleryImage.DeletionStatus.PROVIDER_DELETED,
                            deletion_error='',
                        )
                    for public_id, error in failed.items():
                        image_id = public_to_id.get(public_id)
                        if image_id:
                            EventGalleryImage.objects.filter(pk=image_id).update(
                                deletion_status=EventGalleryImage.DeletionStatus.ACTIVE,
                                deletion_error=(
                                    'This image could not be deleted. '
                                    'Check the server logs before retrying.'
                                ),
                                deletion_requested_at=None,
                            )
            except Exception:
                logger.exception(
                    'Gallery deletion provider outcome could not be recorded locally.',
                    extra={
                        'gallery_operation_phase': 'outcome_persistence',
                        'gallery_selected_image_ids': selected_ids,
                        'gallery_provider_deleted_image_ids': sorted(provider_deleted_ids),
                        'gallery_failed_public_ids': sorted(failed),
                        'gallery_actor_id': getattr(request.user, 'pk', None),
                    },
                )
                self.message_user(
                    request,
                    'The deletion outcome could not be recorded. The pending '
                    'records can be retried safely. '
                    'Please contact an administrator before retrying.',
                    level=messages.ERROR,
                )
                return

        deleted = 0
        finalisation_error = False
        if provider_deleted_ids:
            try:
                with transaction.atomic():
                    event_ids = set(EventGalleryImage.objects.filter(
                        pk__in=provider_deleted_ids,
                    ).values_list('event_id', flat=True))
                    list(Events.objects.select_for_update().filter(pk__in=event_ids))
                    confirmed_images = list(
                        EventGalleryImage.objects.select_for_update().filter(
                            pk__in=provider_deleted_ids,
                            deletion_status=EventGalleryImage.DeletionStatus.PROVIDER_DELETED,
                        )
                    )
                    confirmed_ids = [image.pk for image in confirmed_images]
                    list(MediaAsset.objects.select_for_update().filter(
                        source_event_image_id__in=confirmed_ids,
                    ))
                    newly_protected = event_image_ids_with_editorial_usage(
                        confirmed_ids
                    )
                    if newly_protected:
                        raise ValidationError(
                            'A deletion-pending image acquired editorial usage unexpectedly.'
                        )
                    MediaAsset.objects.filter(
                        source_event_image_id__in=confirmed_ids,
                    ).delete()
                    deleted = EventGalleryImage.objects.filter(
                        pk__in=confirmed_ids,
                    ).delete()[0]
            except Exception:
                finalisation_error = True
                logger.exception(
                    'Gallery deletion local finalisation failed after provider confirmation.',
                    extra={
                        'gallery_operation_phase': 'local_finalisation',
                        'gallery_selected_image_ids': selected_ids,
                        'gallery_provider_deleted_image_ids': sorted(provider_deleted_ids),
                        'gallery_actor_id': getattr(request.user, 'pk', None),
                    },
                )
                try:
                    EventGalleryImage.objects.filter(
                        pk__in=provider_deleted_ids,
                        deletion_status=EventGalleryImage.DeletionStatus.PROVIDER_DELETED,
                    ).update(
                        deletion_error=(
                            'Local deletion finalisation failed. '
                            'Check the server logs, then retry the delete action.'
                        )
                    )
                except Exception:
                    logger.exception('Could not record gallery deletion finalisation failure.')
        if protected_ids:
            self.message_user(
                request,
                f'{len(protected_ids)} image(s) are used by editorial media and were not deleted.',
                level=messages.ERROR,
            )
        if in_progress_ids:
            self.message_user(
                request,
                f'{len(in_progress_ids)} image deletion(s) are already in progress.',
            )
        if deleted:
            self.message_user(request, f'{deleted} image(s) deleted.')
            _log_gallery_action(
                request, 'images_deleted', image_ids=provider_deleted_ids,
                event_ids=event_ids, count=deleted,
            )
        if finalisation_error:
            self.message_user(
                request,
                'Deletion is still being finalised. '
                'Contact an administrator to check the server logs before retrying.',
                level=messages.ERROR,
            )
        if failed:
            self.message_user(
                request,
                f'{len(failed)} image(s) were not deleted and remain active.',
                level=messages.ERROR,
            )

    def save_model(self, request, obj, form, change):
        original = None
        cloudinary_metadata_changed = False
        provider_action_applied = False
        try:
            with transaction.atomic():
                if change:
                    event_ids = {obj.event_id}
                    original_event_id = EventGalleryImage.objects.filter(
                        pk=obj.pk,
                    ).values_list('event_id', flat=True).first()
                    if original_event_id:
                        event_ids.add(original_event_id)
                    list(Events.objects.select_for_update().filter(pk__in=event_ids))
                    original = (
                        EventGalleryImage.objects.select_for_update()
                        .select_related('event').get(pk=obj.pk)
                    )
                    if (
                        original.deletion_status
                        != EventGalleryImage.DeletionStatus.ACTIVE
                    ):
                        raise ValidationError(
                            'This image has a deletion operation in progress. '
                            'Resume or resolve deletion before editing it.'
                        )
                if (
                    original
                    and is_event_image_effectively_public(original)
                    and not is_event_image_effectively_public(obj)
                ):
                    validate_event_images_can_be_made_private([original])
                cloudinary_metadata_changed = change and {
                    'alt_text', 'tags_text', 'event',
                }.intersection(form.changed_data)
                if cloudinary_metadata_changed:
                    update_event_image_metadata(
                        obj.event, obj.public_id, alt_text=obj.alt_text,
                        caption='', tags=obj.tags, is_public=obj.is_public,
                    )
                    provider_action_applied = True
                elif change and 'is_public' in form.changed_data:
                    publication_action = add_publication_tag if obj.is_public else remove_publication_tag
                    publication_action([obj.public_id])
                    provider_action_applied = True
                super().save_model(request, obj, form, change)
                if change:
                    _log_gallery_action(
                        request, 'image_updated', image_ids=[obj.pk],
                        event_ids=[obj.event_id], count=1,
                    )
        except Exception:
            if provider_action_applied and cloudinary_metadata_changed and original:
                try:
                    update_event_image_metadata(
                        original.event, original.public_id,
                        alt_text=original.alt_text, caption='', tags=original.tags,
                        is_public=original.is_public,
                    )
                except Exception:
                    logger.exception('Could not restore Cloudinary image metadata after a database failure.')
            elif (
                provider_action_applied and change
                and 'is_public' in form.changed_data and original
            ):
                compensation = add_publication_tag if original.is_public else remove_publication_tag
                try:
                    compensation([original.public_id])
                except Exception:
                    logger.exception('Could not restore Cloudinary publication state after a database failure.')
            raise

    def _owned_batch(self, request, batch_id):
        batch = get_object_or_404(GalleryUploadBatch, pk=batch_id)
        if batch.created_by_id != request.user.pk:
            raise PermissionDenied
        return batch

    def upload_view(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        stale_batches = GalleryUploadBatch.objects.filter(
            created_at__lt=timezone.now() - timedelta(hours=24),
        )
        for batch in stale_batches:
            batch.delete()
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'events': Events.objects.order_by('-event_date', 'title'),
            'selected_event': request.GET.get('event', ''),
            'stage_url': reverse('admin:events_eventgalleryimage_stage'),
            'commit_url': reverse('admin:events_eventgalleryimage_commit'),
            'remove_url': reverse('admin:events_eventgalleryimage_remove_staged'),
            'cancel_url': reverse('admin:events_eventgalleryimage_cancel_batch'),
            'list_url': reverse('admin:events_eventgalleryimage_changelist'),
            'title': 'Add gallery images',
        }
        return render(request, 'admin/events/eventgalleryimage/upload.html', context)

    def stage_view(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        files = request.FILES.getlist('images')
        if not files:
            return JsonResponse({'ok': False, 'error': 'Choose at least one image.'}, status=400)
        if len(files) > settings.OEF_EVENT_MEDIA_MAX_BATCH_FILES:
            return JsonResponse({
                'ok': False,
                'error': (
                    f'Choose no more than {settings.OEF_EVENT_MEDIA_MAX_BATCH_FILES} '
                    'images in one batch.'
                ),
            }, status=400)
        batch_bytes = sum(uploaded.size for uploaded in files)
        if batch_bytes > settings.OEF_EVENT_MEDIA_MAX_BATCH_BYTES:
            return JsonResponse({
                'ok': False,
                'error': 'The selected images exceed the maximum combined batch size.',
            }, status=400)
        valid = []
        errors = []
        for uploaded in files:
            try:
                validate_editorial_image(uploaded, max_bytes=settings.OEF_EVENT_MEDIA_MAX_BYTES)
            except ValidationError as exc:
                errors.append(f'{uploaded.name}: {" ".join(exc.messages)}')
            else:
                valid.append(uploaded)
        if errors:
            return JsonResponse({'ok': False, 'errors': errors}, status=400)
        batch = GalleryUploadBatch.objects.create(created_by=request.user)
        items = []
        for uploaded in valid:
            item = GalleryUploadItem.objects.create(
                batch=batch, staged_file=uploaded,
                original_filename=Path(uploaded.name).name[:255],
            )
            items.append({
                'id': item.pk, 'name': item.original_filename,
                'preview_url': reverse(
                    'admin:events_eventgalleryimage_preview',
                    args=(batch.pk, item.pk),
                ),
            })
        return JsonResponse({'ok': True, 'batch_id': str(batch.pk), 'items': items}, status=201)

    def preview_view(self, request, batch_id, item_id):
        batch = self._owned_batch(request, batch_id)
        item = get_object_or_404(batch.items, pk=item_id)
        content_type = mimetypes.guess_type(item.original_filename)[0] or 'application/octet-stream'
        response = FileResponse(item.staged_file.open('rb'), content_type=content_type)
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Disposition'] = f'inline; filename="preview-{item.pk}"'
        return response

    def remove_staged_view(self, request):
        batch = self._owned_batch(request, request.POST.get('batch_id'))
        item = get_object_or_404(batch.items, pk=request.POST.get('item_id'))
        item.delete()
        if not batch.items.exists():
            batch.delete()
        return JsonResponse({'ok': True})

    def cancel_batch_view(self, request):
        batch = self._owned_batch(request, request.POST.get('batch_id'))
        for item in list(batch.items.all()):
            item.delete()
        batch.delete()
        return JsonResponse({'ok': True})

    def commit_view(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        batch = self._owned_batch(request, request.POST.get('batch_id'))
        if batch.created_at < timezone.now() - timedelta(hours=24):
            batch.delete()
            messages.error(request, 'This upload batch expired. Add the images again to continue.')
            return HttpResponseRedirect(reverse('admin:events_eventgalleryimage_upload'))
        event = get_object_or_404(Events, pk=request.POST.get('event'))
        tags = [value.strip() for value in request.POST.get('tags', '').split(',') if value.strip()]
        items = list(batch.items.all())
        uploaded = 0
        uploaded_ids = []
        if not items:
            batch.delete()
            messages.error(request, 'There are no staged images to upload.')
            return HttpResponseRedirect(reverse('admin:events_eventgalleryimage_upload'))

        def upload_item(item):
            with item.staged_file.storage.open(item.staged_file.name, 'rb') as source:
                return upload_event_image(
                    event, File(source, name=item.original_filename),
                    alt_text=request.POST.get(f'alt_text_{item.pk}', ''),
                    caption='', tags=tags,
                )

        workers = min(4, len(items))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(upload_item, item): item for item in items}
            for future in as_completed(futures):
                item = futures[future]
                asset = None
                try:
                    asset = future.result()
                    record = EventGalleryImage.objects.create(
                        event=event, asset_id=asset.asset_id, public_id=asset.public_id,
                        secure_url=asset.url, original_filename=item.original_filename,
                        width=asset.width, height=asset.height, alt_text=asset.alt,
                        tags=gallery_user_tags(event, asset.tags), is_public=False,
                        uploaded_by=request.user,
                    )
                    uploaded_ids.append(record.pk)
                    uploaded += 1
                except Exception:
                    logger.exception('Event gallery image upload failed for %s.', item.original_filename)
                    if asset:
                        try:
                            delete_event_images([asset.public_id])
                        except Exception:
                            pass
                    messages.error(request, f'{item.original_filename} could not be uploaded. Please try again.')
                finally:
                    item.delete()
        if not batch.items.exists():
            batch.delete()
        if uploaded:
            messages.success(
                request,
                f'{uploaded} image(s) uploaded. You can edit or publish them below.',
            )
            _log_gallery_action(
                request, 'images_uploaded', image_ids=uploaded_ids,
                event_ids=[event.pk], count=uploaded,
            )
        return HttpResponseRedirect(
            f'{reverse("admin:events_eventgalleryimage_changelist")}?event__id__exact={event.pk}'
        )
