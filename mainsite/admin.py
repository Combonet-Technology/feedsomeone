from django.contrib import admin
from import_export.admin import ImportExportActionModelAdmin

from .models import GalleryImage, TransactionHistory

# Register your models here.
admin.site.register([GalleryImage], ImportExportActionModelAdmin)


@admin.register(TransactionHistory)
class TransactionHistoryAdmin(ImportExportActionModelAdmin):
    list_display = ('tx_status', 'tx_ref', 'tr_id', 'amount', 'date_created')
    list_filter = ('tx_status',)
    search_fields = ('tx_ref', 'tr_id', 'amount')
