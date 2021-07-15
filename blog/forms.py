from django.forms import Select
from django_summernote.widgets import SummernoteWidget, SummernoteInplaceWidget

from .models import Comments, Categories, Post
from django import forms


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comments
        fields = ('name', 'email', 'body', 'website')


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('post_title', 'post_excerpt', 'post_content', 'feature_img')
        widgets = {
            'post_content': SummernoteWidget(attrs={'width': '100%',
                                                    'height': '480px',
                                                    'required': True,
                                                    'placeholder': 'Your name'}),
            # 'post_content': SummernoteInplaceWidget(),
        }


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