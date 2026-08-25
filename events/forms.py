from django import forms

from events.models import EventGalleryImage


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
