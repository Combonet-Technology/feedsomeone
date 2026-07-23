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


class VolunteerOfferForm(forms.Form):
    start_date = forms.DateField(
        label='Engagement start date',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    initial_period = forms.CharField(label='Initial engagement period', max_length=120)
    weekly_commitment = forms.CharField(max_length=160)
    work_arrangement = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))
    reporting_contact = forms.CharField(max_length=255)
    role_contribution = forms.CharField(
        label='Role contribution',
        help_text=(
            'Use one concise sentence describing the main contribution this role will make.'
        ),
        widget=forms.Textarea(attrs={'rows': 4}),
    )
    acceptance_deadline = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    confirm_send = forms.BooleanField(
        label=(
            'I have reviewed the recipient, role and engagement terms and confirm '
            'that this offer is ready to send.'
        ),
    )
