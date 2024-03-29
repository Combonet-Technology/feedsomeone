import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.urls import reverse
from django.utils import timezone
from taggit.managers import TaggableManager

from user.models import UserProfile


class Categories(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated at")
    title = models.CharField(max_length=255, verbose_name="Title", default='UNCATEGORIZED')

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['title']

    def __str__(self):
        return self.title


class PublishedManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_published=True, is_deleted=False).order_by('-publish_date')


class Article(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    article_title = models.CharField(max_length=100, null=False, blank=False)
    article_excerpt = models.CharField(max_length=255, null=True, blank=True)
    article_slug = models.SlugField(null=False, unique=True, max_length=150)
    article_content = models.TextField()
    feature_img = models.ImageField(upload_to='article_feature_img', default='feature_default.jpg')
    article_author = models.ForeignKey(UserProfile,
                                       on_delete=models.CASCADE,
                                       null=True,
                                       blank=True,
                                       related_name="user_article")
    category = models.ManyToManyField(Categories, blank=True, verbose_name="Category", related_name="article")
    is_published = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    publish_date = models.DateTimeField(default=timezone.now)
    date_created = models.DateTimeField(auto_now_add=True, verbose_name="Created_at")
    date_updated = models.DateTimeField(auto_now=True, verbose_name="Updated_at")

    published = PublishedManager()
    objects = models.Manager()
    tags = TaggableManager()

    def __str__(self):
        return self.article_title

    def get_absolute_url(self):
        return reverse('article:article_detail',
                       args=[self.publish_date.year,
                             self.publish_date.month,
                             self.publish_date.day,
                             self.article_slug])

    def to_dict(self):
        return {
            'uuid': str(self.uuid),
            # 'article_title': self.article_title,
            'article_slug': self.article_slug,
            # 'article_content': self.article_content,
            'feature_img': self.feature_img.url if self.feature_img else None,
            'article_author': self.article_author.get_full_name() if self.article_author else None,
            'category': [category.title for category in self.category.all()],
            'is_published': self.is_published,
            'is_deleted': self.is_deleted,
            # 'publish_date': self.publish_date.isoformat(),
            # 'date_created': self.date_created.isoformat(),
            # 'date_updated': self.date_updated.isoformat(),
            'tags': list(self.tags.names()),
        }


#     override save method to autogenerate slug

class Comments(models.Model):
    post = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=80)
    email = models.EmailField()
    body = models.TextField()
    website = models.CharField(max_length=100)
    created_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_on']

    def __str__(self):
        return f'Comment {self.body} by {self.name}'


class InnerComments(models.Model):
    post = models.ForeignKey(Comments, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=80)
    email = models.EmailField()
    body = models.TextField()
    # website = models.CharField(max_length=100)
    created_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    def __str__(self):
        return f'reply {self.body} to {self.post}'
