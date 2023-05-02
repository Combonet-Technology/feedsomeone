from django.contrib import admin
# from django_summernote.admin import SummernoteModelAdmin
from import_export.admin import ImportExportActionModelAdmin

from blog.models import Article, Categories, Comments


@admin.register(Article)
class ArticleAdmin(ImportExportActionModelAdmin):
    # summernote_fields = '__all__'
    summernote_fields = ('post_content',)
    list_display = ('article_title', 'article_slug', 'article_excerpt', 'article_author', 'status', 'publish')
    list_filter = ('publish', 'created', 'article_author', 'status')
    search_fields = ('title', 'body')
    prepopulated_fields = {'article_slug': ('article_title',)}
    raw_id_fields = ('article_author',)
    date_hierarchy = 'publish'
    ordering = ('status', 'publish')

    def publish_article(self, request, queryset):
        queryset.update(status=True)

    def unpublish_article(self, request, queryset):
        queryset.update(status=False)


@admin.register(Categories)
class CategoriesAdmin(ImportExportActionModelAdmin):
    list_display = ['title']
    search_fields = ['title']


@admin.register(Comments)
class CommentAdmin(ImportExportActionModelAdmin):
    list_display = ('name', 'body', 'post', 'created_on', 'website', 'active')
    list_filter = ('active', 'created_on')
    search_fields = ('name', 'email', 'body')
    actions = ['approve_comments']

    def approve_comments(self, request, queryset):
        queryset.update(active=True)
