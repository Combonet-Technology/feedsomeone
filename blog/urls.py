from django.urls import path

from . import views
from .views import (ArticleDeleteView, ArticleListView, UpdateArticleView,
                    UserArticleListView)

app_name = 'article'

urlpatterns = [
    path('create/', views.create_article, name="create-article"),
    # path('create-article', CreateArticleView.as_view(), name="create-article"),
    path('all/', ArticleListView.as_view(), name="all-articles"),
    # path('article/<int:pk>', ArticleDetailView.as_view(), name="full-article"),
    path('<int:pk>/update/', UpdateArticleView.as_view(), name="update-post"),
    path('<int:pk>/<slug:slug>/', views.article_detail, name='article-detail'),
    path('<int:year>/<int:month>/<int:day>/<slug:post>/', views.article_detail, name='article_detail'),
    path('<str:username>/', UserArticleListView.as_view(), name="article-by-user"),
    path('<int:pk>/delete/', ArticleDeleteView.as_view(), name="delete-post"),
    # path('inspiration/', views.about, name="inspiration"),
    # path('testimonials/', views.about, name="testimonials"),
    # path('all-posts', ArticleListView.as_view(template_name='all-post.html'), name="all-posts"),
    # path('all-posts', views.all_post, name="all-posts"),
    # path('single/', views.single_post, name="full-post"),
    # path('enquiry', views.enquiry, name="contact"),
]

# blog/article_list.html
# <app>/<model>_<viewtype>.html
