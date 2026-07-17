from django.urls import path

from . import views

app_name = 'opportunities'

urlpatterns = [
    path('', views.VacancyListView.as_view(), name='list'),
    path('<slug:slug>/', views.VacancyDetailView.as_view(), name='detail'),
    path('<slug:slug>/apply/', views.apply, name='apply'),
]
