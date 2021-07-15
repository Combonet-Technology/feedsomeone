from django.contrib import admin
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse


# Create your models here.
# class Category(models.Model):
#     category_title = models.CharField(max_length=30, default='UNCATEGORIZED')
#     category_posts = models.ForeignKey(Post, on_delete=models.CASCADE)
#     date_created = models.DateTimeField(default=timezone.now)


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


class Post(models.Model):
    post_title = models.CharField(max_length=100)
    post_excerpt = models.CharField(max_length=150)
    post_content = models.TextField()
    feature_img = models.ImageField(upload_to='article_feature_img', default='feature_default.jpg')
    date_posted = models.DateTimeField(default=timezone.now)
    post_author = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Categories, verbose_name="Category", on_delete=models.DO_NOTHING)

    # post_categories = models.ForeignKey(Category, on_delete=models.SET_DEFAULT, default='UNCATEGORIZED')
    # post_tags = models.ForeignKey(Taggs, on_delete=models.SET_DEFAULT, default='UNCATEGORIZED')

    def __str__(self):
        return self.post_title

    def get_absolute_url(self):
        return reverse('full-article', kwargs={'pk': self.pk})

# class Taggs(models.Model):
#     tag_title = models.CharField(max_length=30, default='UNCATEGORIZED')
#     tag_posts = models.ForeignKey(Post, on_delete=models.CASCADE)
#     date_created = models.DateTimeField(default=timezone.now)


class Comments(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=80)
    email = models.EmailField()
    body = models.TextField()
    website = models.CharField(max_length=100)
    created_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_on']

    def __str__(self):
        return 'Comment {} by {}'.format(self.body, self.name)


class InnerComments(models.Model):
    post = models.ForeignKey(Comments, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=80)
    email = models.EmailField()
    body = models.TextField()
    # website = models.CharField(max_length=100)
    created_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    def __str__(self):
        return 'reply {} to {}'.format(self.body, self.post)




