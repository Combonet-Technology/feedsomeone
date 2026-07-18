from django import forms

from .models import VacancyApplication


class VacancyApplicationForm(forms.ModelForm):
    consent = forms.BooleanField(
        label='I consent to OEF using these details to assess this application.',
    )
    newsletter_opt_in = forms.BooleanField(
        required=False,
        label=(
            'Send me OEF news and programme updates. '
            'I can unsubscribe at any time.'
        ),
    )

    class Meta:
        model = VacancyApplication
        fields = (
            'full_name',
            'email',
            'phone',
            'cv',
            'cover_letter',
            'newsletter_opt_in',
        )
        labels = {
            'full_name': 'Full name',
            'phone': 'Phone number (optional)',
            'cv': 'CV or resume',
            'cover_letter': 'Why would you like to join OEF?',
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'phone': forms.TextInput(attrs={'autocomplete': 'tel'}),
            'cover_letter': forms.Textarea(attrs={'rows': 7}),
        }

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_cv(self):
        cv = self.cleaned_data['cv']
        if not cv.name.lower().endswith(('.pdf', '.doc', '.docx')):
            raise forms.ValidationError('Upload your CV as a PDF, DOC, or DOCX file.')
        if cv.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Your CV must be 5 MB or smaller.')
        return cv
