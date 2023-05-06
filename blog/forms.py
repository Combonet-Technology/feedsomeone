from django import forms
from django.forms.widgets import HiddenInput
from django.template.defaultfilters import slugify
from django_summernote.widgets import SummernoteWidget

from .models import Article, Comments


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comments
        fields = ('name', 'email', 'body', 'website')


class ArticleForm(forms.ModelForm):
    article_slug = forms.CharField(required=False)

    class Meta:
        model = Article
        fields = ('article_title', 'article_excerpt', 'article_slug',
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
        print(cleaned_data)
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

# class CategoryForm(forms.ModelForm):
#     class Meta:
#         model = Categories
#         # fields = ('title',)
#         CHOICES = {}
#         categories = Categories.objects.all()
#         for category in categories:
#             CHOICES[category] = category.id
#         widgets = {
#             'name': Select(attrs={'cols': 50, 'rows': 20}),
#             'choices': CHOICES,
#         }
#         # exit(CHOICES)
#         fields = forms.ChoiceField(choices=CHOICES)
#         select = forms.CharField(widget=forms.Select(choices=CHOICES))
