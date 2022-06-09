from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import VolunteerListView, VolunteerDetailView, activate

urlpatterns = [
    path('register/', views.register, name="register"),
    path(r'activate/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/',
         activate, name='activate'),
    path('profile/', views.profile, name="profile"),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name="login"),
    path('view-volunteers/', VolunteerListView.as_view(), name="volunteer-list"),
    path('view-volunteers/<int:pk>/', VolunteerDetailView.as_view(), name="volunteer-details"),
    path('logout/', auth_views.LogoutView.as_view(template_name='logout.html'), name="logout"),
    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='password_reset.html'),
         name="password_reset"),
    path('password-reset/confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'),
         name="password_reset_confirm"),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
         name="password_reset_done"),
    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),
         name="password_reset_complete"),
]
