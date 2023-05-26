from django.urls import path

from . import views

urlpatterns = [
    path('register/', views.register, name="register"),
    path('create_username/', views.create_username, name="create_username"),
    path('check_username_availability/', views.check_username_availability, name='check_username_availability'),
    path('activate/<slug:uidb64>/<slug:token>/', views.activate, name='activate'),
    path('profile/', views.profile, name="profile"),
    path('change-pass/', views.set_password_view, name="create_private_pass"),
    path('change-pass/reset/<uidb64>/<token>/', views.set_password_view, name="create_private_pass"),
    path('view-volunteers/', views.VolunteerListView.as_view(), name="volunteer-list"),
    path('view-volunteers/<int:pk>/', views.VolunteerDetailView.as_view(), name="volunteer-details"),
    path('password_reset/', views.InitiatePasswordReset.as_view(), name='reset_user_password'),
]
