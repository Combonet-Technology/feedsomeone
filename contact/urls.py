from django.urls import path

from . import views

urlpatterns = [
    path('', views.contact, name="contact"),
    path('thanks/', views.thanks, name="thanks"),
    path('subscribe/', views.newsletter_signup, name='newsletter'),
]
