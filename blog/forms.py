from django_summernote.widgets import SummernoteWidget, SummernoteInplaceWidget
from django.template.defaultfilters import slugify
from .models import Comments, Categories, Article
from django import forms
from django.forms.widgets import HiddenInput


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comments
        fields = ('name', 'email', 'body', 'website')


class ArticleForm(forms.ModelForm):
    article_slug = forms.CharField(required=False)

    class Meta:
        model = Article
        fields = ('article_title', 'article_excerpt', 'article_slug', 'article_content', 'feature_img')
        # exclude = ['article_slug']
        widgets = {
            'article_content': SummernoteWidget(attrs={'width': '100%',
                                                    'height': '480px',
                                                    'required': True,
                                                    'placeholder': 'Your name'}),
        }

    def __init__(self, *args, **kwargs):
        super(ArticleForm, self).__init__(*args, **kwargs)
        self.fields['article_slug'].widget = HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        print(cleaned_data)
        title = cleaned_data.get("article_title")

        if title:
            cleaned_data['article_slug'] = slugify(title)
            return self.cleaned_data



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