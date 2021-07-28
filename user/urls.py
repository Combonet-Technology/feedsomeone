from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from .views import VolunteerListView, VolunteerDetailView

urlpatterns = [
    path('register/', views.register, name="register"),
    path('profile/', views.profile, name="profile"),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name="login"),
    path('view-volunteers/', VolunteerListView.as_view(), name="volunteer-list"),
    path('view-volunteers/<int:pk>', VolunteerDetailView.as_view(), name="volunteer-details"),
    path('logout/', auth_views.LogoutView.as_view(template_name='logout.html'), name="logout"),
    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='password_reset.html'),
         name="password_reset"),
    path('password-reset/confirm/<uidb64>/<token>',
         auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'),
         name="password_reset_confirm"),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
         name="password_reset_done"),
    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),
         name="password_reset_complete"),
    # path('', views.entry, name="entry"),
]
