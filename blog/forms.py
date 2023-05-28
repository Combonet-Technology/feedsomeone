from django import forms
from django.forms.widgets import HiddenInput
from django.template.defaultfilters import slugify
from django_summernote.widgets import SummernoteWidget

from .models import Article, Categories, Comments


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comments
        fields = ('name', 'email', 'body', 'website')


class ArticleForm(forms.ModelForm):
    article_slug = forms.SlugField()

    class Meta:
        model = Article
        fields = ('article_title', 'article_excerpt',
                  'article_content', 'category', 'feature_img')
        widgets = {
            'article_content': SummernoteWidget(
                attrs={'width': '100%',
                       'height': '480px',
                       'required': True,
                       'placeholder': 'Type in your content here, you can format like Ms word'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['article_slug'].widget = HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get("article_title")

        if title:
            cleaned_data['article_slug'] = slugify(title)
            return self.cleaned_data


class EmailShareForm(forms.Form):
    name = forms.CharField(max_length=25)
    email = forms.EmailField()
    to = forms.EmailField()
    comments = forms.CharField(required=False,
                               widget=forms.Textarea)


class SearchForm(forms.Form):
    query = forms.CharField()


class CategoryForm(forms.ModelForm):
    new_category = forms.CharField(max_length=100, required=False)

    class Meta:
        model = Categories
        fields = ('title',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget = forms.CheckboxSelectMultiple()

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_category = self.cleaned_data.get('new_category')
        if new_category:
            instance.name = new_category
            if commit:
                instance.save()
        return instance
