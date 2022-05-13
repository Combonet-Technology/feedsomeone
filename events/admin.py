from django.contrib import admin

# Register your models here.
from import_export.admin import ImportExportActionModelAdmin

from events.models import Events

admin.site.register([Events], ImportExportActionModelAdmin)