from django import forms
from django.template.defaultfilters import slugify

from .models import Article, Categories, Comments


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comments
        fields = ('name', 'email', 'body', 'website')
        widgets = {
            'website': forms.URLInput(attrs={'placeholder': 'Website (optional)'}),
        }


class ArticleForm(forms.ModelForm):
    clear_feature_image = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].widget = forms.CheckboxSelectMultiple()
        self.fields['category'].queryset = Categories.objects.all()
        self.fields['category'].help_text = 'Choose up to four categories.'
        self.fields['tags'].help_text = 'Type a tag, then press Enter or comma.'
        self.fields['article_title'].widget.attrs.update({
            'placeholder': 'Write a clear, specific headline',
            'autocomplete': 'off',
        })
        self.fields['article_excerpt'].widget.attrs.update({
            'placeholder': 'Summarise the article in one or two sentences',
        })
        self.fields['tags'].widget.attrs.update({
            'placeholder': 'Add a tag and press Enter',
            'autocomplete': 'off',
        })
        self.fields['feature_media'].widget = forms.HiddenInput()
        self.fields['feature_crop'].widget = forms.HiddenInput()

        if self.instance.pk:
            self.initial['category'] = self.instance.category.values_list('id', flat=True)

    class Meta:
        model = Article
        fields = (
            'feature_media',
            'feature_crop',
            'clear_feature_image',
            'article_title',
            'article_excerpt',
            'article_content',
            'tags',
            'category',
        )

    def clean(self):
        cleaned_data = super().clean()

        selected_categories = cleaned_data.get("category")
        if selected_categories:
            if selected_categories and len(selected_categories) > 4:
                self.add_error('category', "You can select a maximum of 4 categories.")
        return cleaned_data

    def save(self, commit=True):
        article = super().save(commit=False)
        if self.cleaned_data.get('clear_feature_image'):
            article.feature_media = None
            article.feature_crop = {}
            article.feature_img = ''
        elif article.feature_media_id:
            article.feature_img = ''
        if not article.article_slug:
            base_slug = slugify(article.article_title) or 'article'
            candidate = base_slug
            suffix = 2
            existing = Article.objects.exclude(pk=article.pk)
            while existing.filter(article_slug=candidate).exists():
                candidate = f'{base_slug}-{suffix}'
                suffix += 1
            article.article_slug = candidate
        if commit:
            article.save()
            self.save_m2m()
        return article


class EmailShareForm(forms.Form):
    name = forms.CharField(max_length=25)
    email = forms.EmailField()
    to = forms.EmailField()
    comments = forms.CharField(required=False,
                               widget=forms.Textarea)


class SearchForm(forms.Form):
    query = forms.CharField()
