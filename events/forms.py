from django import forms
from django.core.exceptions import ValidationError

from blog.media import validate_event_images_can_be_made_private
from events.models import EventGalleryImage, Events


class EventsAdminForm(forms.ModelForm):
    """Surface gallery publication invariants as actionable form errors."""

    class Meta:
        model = Events
        fields = '__all__'

    def clean_gallery_is_public(self):
        gallery_is_public = self.cleaned_data['gallery_is_public']
        if gallery_is_public or not self.instance.pk:
            return gallery_is_public

        was_public = Events.objects.filter(pk=self.instance.pk).values_list(
            'gallery_is_public', flat=True,
        ).first()
        if not was_public:
            return gallery_is_public

        public_images = EventGalleryImage.objects.filter(
            event_id=self.instance.pk,
            is_public=True,
            deletion_status=EventGalleryImage.DeletionStatus.ACTIVE,
        )
        try:
            validate_event_images_can_be_made_private(public_images)
        except ValidationError as exc:
            raise ValidationError(' '.join(exc.messages)) from exc

        return gallery_is_public


class EventGalleryImageAdminForm(forms.ModelForm):
    tags_text = forms.CharField(
        required=False,
        label='Tags',
        help_text='Comma-separated descriptive tags. The event and environment tags are applied automatically.',
        widget=forms.TextInput(attrs={'placeholder': 'volunteers, food-relief'}),
    )

    class Meta:
        model = EventGalleryImage
        exclude = ('tags',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['tags_text'].initial = ', '.join(self.instance.tags or [])

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tags = [
            value.strip() for value in self.cleaned_data.get('tags_text', '').split(',')
            if value.strip()
        ]
        if commit:
            instance.save()
            self.save_m2m()
        return instance
