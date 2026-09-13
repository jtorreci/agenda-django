from django.contrib import admin

from .models import Asignatura, CatalogueImport, CatalogueImportRow, Titulacion

admin.site.register(Titulacion)
admin.site.register(Asignatura)


class CatalogueImportRowInline(admin.TabularInline):
    model = CatalogueImportRow
    extra = 0
    raw_id_fields = ('target_titulacion', 'target_asignatura')


@admin.register(CatalogueImport)
class CatalogueImportAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'source_filename', 'state', 'created_by', 'created_at', 'applied_at')
    list_filter = ('state', 'academic_year')
    inlines = [CatalogueImportRowInline]


@admin.register(CatalogueImportRow)
class CatalogueImportRowAdmin(admin.ModelAdmin):
    list_display = ('catalogue_import', 'plan_code', 'subject_code', 'subject_name', 'curricular_year', 'semester', 'match_status')
    list_filter = ('match_status', 'catalogue_import')
    search_fields = ('plan_code', 'plan_name', 'subject_code', 'subject_name')
    raw_id_fields = ('target_titulacion', 'target_asignatura')
