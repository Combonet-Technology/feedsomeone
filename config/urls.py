"""config URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import debug_toolbar
from baton.autodiscover import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from blog.sitemaps import ArticleSitemap
from user.views import social_auth_complete

sitemaps = {
    'articles': ArticleSitemap,
}

urlpatterns = [

    path('baton/', include('baton.urls')),
    path('bcx/', admin.site.urls),
    path('', include('mainsite.urls')),
    path('', include('events.urls')),
    path('contact/', include('contact.urls')),
    path('volunteers/', include('user.urls')),
    path('article/', include('blog.urls', namespace='article')),
    path('imagefit/', include('imagefit.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    path('', include('django.contrib.auth.urls')),
    path(f'social-auth/complete/<str:backend>/', social_auth_complete, name='complete'),
    path('social-auth/', include('social_django.urls', namespace='social')),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    # re_path(r'^', include('cms.urls'))
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += path('__debug__/', include(debug_toolbar.urls)),

handler404 = 'errors.views.handler404'
handler500 = 'errors.views.handler500'
handler403 = 'errors.views.handler403'
handler400 = 'errors.views.handler400'
