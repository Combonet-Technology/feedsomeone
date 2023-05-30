from django import forms
from django.template.defaultfilters import slugify
from django_summernote.widgets import SummernoteWidget
from taggit.forms import TagWidget

from .models import Article, Categories, Comments


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comments
        fields = ('name', 'email', 'body', 'website')


class ArticleForm(forms.ModelForm):
    tags = forms.CharField(widget=TagWidget())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].widget = forms.CheckboxSelectMultiple()
        self.fields['category'].queryset = Categories.objects.all()

        if self.instance.pk:
            self.initial['tags'] = ', '.join(self.instance.tags.names())
            self.initial['category'] = self.instance.category.values_list('id', flat=True)

    class Meta:
        model = Article
        fields = ('feature_img', 'article_title', 'article_content', 'tags', 'category')
        widgets = {
            'article_content': SummernoteWidget(
                attrs={'width': '100%',
                       'height': '480px',
                       'required': True,
                       'placeholder': 'Type in your content here, you can format like Ms word'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        selected_categories = cleaned_data.get("category")
        if selected_categories:
            if selected_categories and len(selected_categories) > 4:
                self.add_error('category', "You can select a maximum of 4 categories.")

        return cleaned_data

    def save(self, commit=True):
        article = super().save(commit=False)
        slug = slugify(article.article_title)
        article.article_slug = slug
        if commit:
            article.save()
        return article


class EmailShareForm(forms.Form):
    name = forms.CharField(max_length=25)
    email = forms.EmailField()
    to = forms.EmailField()
    comments = forms.CharField(required=False,
                               widget=forms.Textarea)


class SearchForm(forms.Form):
    query = forms.CharField()
