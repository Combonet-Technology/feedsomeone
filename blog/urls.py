from django.urls import path

from . import views
from .rss_feeds import LatestArticlesFeed
from .views import (ArticleDeleteView, ArticleListView, UpdateArticleView,
                    UserArticleListView, search_article)

app_name = 'article'
urlpatterns = [
    path('feed/', LatestArticlesFeed(), name='article_feed'),
    path('search/', search_article, name='search_articles'),
    path('create/', views.create_article, name="create-article"),
    path('<slug:slug>/share/', views.post_share, name='post_share'),
    path('<slug:slug>/update/', UpdateArticleView.as_view(), name="update-post"),
    path('<slug:slug>/delete/', ArticleDeleteView.as_view(), name="delete-post"),
    path('<int:year>/<int:month>/<int:day>/<slug:slug>/', views.article_detail, name='article_detail'),
    path('all/', ArticleListView.as_view(), name="all-articles"),
    path('all/<str:category>', ArticleListView.as_view(), name="articles-by-category"),
    path('all/<slug:tag>', ArticleListView.as_view(), name="articles-by-slug"),
    path('<str:username>/', UserArticleListView.as_view(), name="article-by-user"),
]
