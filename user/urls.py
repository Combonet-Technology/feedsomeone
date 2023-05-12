from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .views import VolunteerDetailView, VolunteerListView

urlpatterns = [
    path('register/', views.register, name="register"),
    path('activate/<slug:uidb64>/<slug:token>/', views.activate, name='activate'),
    path('profile/', views.profile, name="profile"),
    path('login/', auth_views.LoginView.as_view(), name="login"),
    path('view-volunteers/', VolunteerListView.as_view(), name="volunteer-list"),
    path('view-volunteers/<int:pk>/', VolunteerDetailView.as_view(), name="volunteer-details"),
    path('logout/', auth_views.LogoutView.as_view(), name="logout"),
    path('password-reset/', auth_views.PasswordResetView.as_view(), name="password_reset"),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete")
]
