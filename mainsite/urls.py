"""feedsomeone URL Configuration

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
from django.contrib import admin
from django.urls import path, include

from . import views
from .views import AllGalleryImagesListView, UpcomingEventsList, EventDetailView, PastEventsList, CreateEventView, \
    AllEventsList

urlpatterns = [
    path('', views.home, name='homepage'),
    path('about/', views.about, name='about-page'),
    path('events/', AllEventsList.as_view(), name='events'),
    # path('contact/', views.contact, name='contact'),
    path('events/upcoming', UpcomingEventsList.as_view(), name="future_events"),
    path('events/past', PastEventsList.as_view(), name="past_events"),
    path('events/<int:pk>', EventDetailView.as_view(), name="event-details"),
    path('add-event', CreateEventView.as_view(), name="new-event"),
    path('gallery/', AllGalleryImagesListView.as_view(), name="gallery"),
    path('donate/', views.donate, name='donate'),
    path('thanks-donation/', views.donate_thanks, name='donate-thanks'),
    path('upload/', views.upload_images, name='imageuploader'),
]

