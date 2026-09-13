from django.contrib import admin

from .models import (
    Asignatura,
    CatalogueImport,
    CatalogueImportPlanOverride,
    CatalogueImportRow,
    PlanCodeAlias,
    Titulacion,
)

admin.site.register(Asignatura)


class PlanCodeAliasInline(admin.TabularInline):
    model = PlanCodeAlias
    extra = 0


@admin.register(Titulacion)
class TitulacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_plan')
    search_fields = ('nombre', 'codigo_plan', 'plan_code_aliases__code')
    inlines = [PlanCodeAliasInline]


@admin.register(PlanCodeAlias)
class PlanCodeAliasAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'titulacion')
    search_fields = ('code', 'name', 'titulacion__nombre')
    autocomplete_fields = ('titulacion',)


class CatalogueImportRowInline(admin.TabularInline):
    model = CatalogueImportRow
    extra = 0
    raw_id_fields = ('target_titulacion', 'target_asignatura')


class CatalogueImportPlanOverrideInline(admin.TabularInline):
    model = CatalogueImportPlanOverride
    extra = 0
    raw_id_fields = ('titulacion',)


@admin.register(CatalogueImport)
class CatalogueImportAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'source_filename', 'state', 'created_by', 'created_at', 'applied_at')
    list_filter = ('state', 'academic_year')
    inlines = [CatalogueImportPlanOverrideInline, CatalogueImportRowInline]


@admin.register(CatalogueImportRow)
class CatalogueImportRowAdmin(admin.ModelAdmin):
    list_display = ('catalogue_import', 'plan_code', 'plan_role', 'subject_code', 'subject_name', 'curricular_year', 'semester', 'match_status')
    list_filter = ('match_status', 'plan_role', 'catalogue_import')
    search_fields = ('plan_code', 'plan_name', 'subject_code', 'subject_name')
    raw_id_fields = ('target_titulacion', 'target_asignatura')
