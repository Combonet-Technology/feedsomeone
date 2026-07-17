from django import forms

from .models import VacancyApplication


class VacancyApplicationForm(forms.ModelForm):
    class Meta:
        model = VacancyApplication
        fields = ('cv', 'cover_letter')
        widgets = {'cover_letter': forms.Textarea(attrs={'rows': 8})}

    def clean_cv(self):
        cv = self.cleaned_data['cv']
        if not cv.name.lower().endswith(('.pdf', '.doc', '.docx')):
            raise forms.ValidationError('Upload your CV as a PDF, DOC, or DOCX file.')
        return cv
