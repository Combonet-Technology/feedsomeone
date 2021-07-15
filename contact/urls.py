from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.contact, name="contact"),
    path('thanks/', views.thanks, name="thanks"),
    # path('enquiry', views.enquiry, name="contact"),
]
