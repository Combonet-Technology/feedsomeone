from django.contrib import admin
from blog.models import Post, Comments, Categories
from django_summernote.admin import SummernoteModelAdmin
from import_export.admin import ImportExportActionModelAdmin, ExportActionModelAdmin


# Register your models here.
# admin.site.register(Post)


# @admin.register(Post)
# class PostAdmin(ImportExportActionModelAdmin):
#     pass


@admin.register(Post)
class PostAdmin(ImportExportActionModelAdmin):
    # summernote_fields = '__all__'
    summernote_fields = ('post_content',)


@admin.register(Categories)
class CategoriesAdmin(ImportExportActionModelAdmin):
    list_display = ['title']
    search_fields = ['title']


@admin.register(Comments)
class CommentAdmin(ImportExportActionModelAdmin):
    list_display = ('name', 'body', 'post', 'created_on','website', 'active')
    list_filter = ('active', 'created_on')
    search_fields = ('name', 'email', 'body')
    actions = ['approve_comments']

    def approve_comments(self, request, queryset):
        queryset.update(active=True)
