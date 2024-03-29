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
from django.contrib import admin
from django.urls import path, include

from events.views import AllEventsList, CreateEventView, EventDetailView, PastEventsList, UpcomingEventsList

urlpatterns = [
    path('events/', AllEventsList.as_view(), name='events'),
    path('events/upcoming', UpcomingEventsList.as_view(), name="future_events"),
    path('events/past', PastEventsList.as_view(), name="past_events"),
    path('events/<int:pk>/<slug:slug>', EventDetailView.as_view(), name="event-details"),
    path('event/add', CreateEventView.as_view(), name="new-event"),
]

