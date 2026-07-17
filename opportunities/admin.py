from django.contrib import admin

from .models import Vacancy, VacancyApplication


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'published_at', 'created_at')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'summary', 'description')


@admin.register(VacancyApplication)
class VacancyApplicationAdmin(admin.ModelAdmin):
    list_display = ('vacancy', 'applicant', 'status', 'created_at')
    list_filter = ('status', 'vacancy')
    search_fields = ('vacancy__title', 'applicant__email', 'applicant__first_name', 'applicant__last_name')
