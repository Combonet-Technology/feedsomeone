from django.urls import path
from .views import (ArticleListView,
                    # ArticleDetailView,
                    # CreateArticleView,
                    UpdateArticleView,
                    ArticleDeleteView,
                    UserArticleListView)
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('create-article', views.create_article, name="create-article"),
    # path('create-article', CreateArticleView.as_view(), name="create-article"),
    path('articles/', ArticleListView.as_view(), name="all-articles"),
    # path('article/<int:pk>', ArticleDetailView.as_view(), name="full-article"),
    path('article/<int:pk>/<slug:slug>', views.article_detail, name='article-detail'),
    path('article/<str:username>', UserArticleListView.as_view(), name="article-by-user"),
    path('single/<int:pk>/update/', UpdateArticleView.as_view(), name="update-post"),
    path('single/<int:pk>/delete/', ArticleDeleteView.as_view(), name="delete-post"),
    # path('inspiration/', views.about, name="inspiration"),
    # path('testimonials/', views.about, name="testimonials"),
    # path('all-posts', ArticleListView.as_view(template_name='all-post.html'), name="all-posts"),
    # path('all-posts', views.all_post, name="all-posts"),
    # path('single/', views.single_post, name="full-post"),
    # path('enquiry', views.enquiry, name="contact"),
]

# blog/post_list.html
# <app>/<model>_<viewtype>.html
