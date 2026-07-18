from django.contrib import admin

from .models import Vacancy, VacancyApplication


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'status',
        'positions_available',
        'is_active',
        'published_at',
        'created_at',
    )
    list_filter = ('status', 'is_active')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'summary', 'description')


@admin.register(VacancyApplication)
class VacancyApplicationAdmin(admin.ModelAdmin):
    list_display = ('vacancy', 'full_name', 'email', 'status', 'created_at')
    list_filter = ('status', 'vacancy')
    search_fields = ('vacancy__title', 'full_name', 'email')
