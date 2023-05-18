from django.urls import path

from . import views
from .views import VolunteerDetailView, VolunteerListView

urlpatterns = [
    path('register/', views.register, name="register"),
    path('activate/<slug:uidb64>/<slug:token>/', views.activate, name='activate'),
    path('profile/', views.profile, name="profile"),
    path('view-volunteers/', VolunteerListView.as_view(), name="volunteer-list"),
    path('view-volunteers/<int:pk>/', VolunteerDetailView.as_view(), name="volunteer-details"),
]
