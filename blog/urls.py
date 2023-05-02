from django.urls import path

from . import views
from .views import (ArticleDeleteView, ArticleListView, UpdateArticleView,
                    UserArticleListView)

app_name = 'article'

urlpatterns = [
    path('create/', views.create_article, name="create-article"),
    path('all/', ArticleListView.as_view(), name="all-articles"),
    path('<int:pk>/update/', UpdateArticleView.as_view(), name="update-post"),
    path('<int:year>/<int:month>/<int:day>/<slug:slug>/', views.article_detail, name='article_detail'),
    path('<str:username>/', UserArticleListView.as_view(), name="article-by-user"),
    path('<int:pk>/delete/', ArticleDeleteView.as_view(), name="delete-post"),
    path('<int:post_id>/share/', views.post_share, name='post_share'),
]
