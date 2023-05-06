from django.urls import path

from . import views
from .rss_feeds import LatestArticlesFeed
from .views import (ArticleDeleteView, ArticleListView, UpdateArticleView,
                    UserArticleListView)

app_name = 'article'
urlpatterns = [
    path('feed/', LatestArticlesFeed(), name='article_feed'),
    path('create/', views.create_article, name="create-article"),
    path('<slug:slug>/share/', views.post_share, name='post_share'),
    path('<int:pk>/update/', UpdateArticleView.as_view(), name="update-post"),
    path('<int:year>/<int:month>/<int:day>/<slug:slug>/', views.article_detail, name='article_detail'),
    path('<int:pk>/delete/', ArticleDeleteView.as_view(), name="delete-post"),
    path('all/', ArticleListView.as_view(), name="all-articles"),
    path('all/<str:category>', ArticleListView.as_view(), name="articles-by-category"),
    path('all/<slug:tag>', ArticleListView.as_view(), name="articles-by-slug"),
    path('<str:username>/', UserArticleListView.as_view(), name="article-by-user"),
]
