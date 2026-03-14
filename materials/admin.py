import csv
import io
import os
import zipfile

from django import forms
from django.contrib import admin
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from .forms import IconPickerWidget
from .models import Comment, Material, MaterialType, SchoolYear, SearchLog, Subject, SubjectVIP, SubjectYear, Tag


class MaterialAdminForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = '__all__'
        widgets = {
            'icon': IconPickerWidget(),
        }


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _export_csv(filename, headers, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')  # BOM for Excel UTF-8
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerows(rows)
    return response


def _export_xlsx(filename, headers, rows):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _material_rows(qs):
    qs = qs.select_related('subject__subject', 'subject__school_year', 'material_type', 'author').annotate(
        like_count=Count('likes', distinct=True)
    )
    rows = []
    for m in qs:
        rows.append([
            m.pk, m.title,
            str(m.subject.school_year), str(m.subject.subject.name),
            str(m.material_type),
            m.author.email if m.author else '',
            m.download_count, m.like_count,
            m.is_published, m.version,
            m.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return rows


MATERIAL_HEADERS = [
    'ID', 'Název', 'Ročník', 'Předmět', 'Typ', 'Autor (email)',
    'Stažení', 'Líbí se', 'Zveřejněno', 'Verze', 'Nahráno',
]


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class SubjectYearInline(TabularInline):
    model = SubjectYear
    fields = ['subject', 'teachers']
    autocomplete_fields = ['subject']
    filter_horizontal = ['teachers']
    extra = 0


class SubjectVIPInline(TabularInline):
    model = SubjectVIP
    fields = ['user', 'granted_by', 'granted_at']
    readonly_fields = ['granted_at']
    autocomplete_fields = ['user']
    extra = 0


class MaterialInline(TabularInline):
    model = Material
    fields = ['title', 'file', 'material_type', 'author', 'is_published']
    extra = 0


class SubjectYearsInline(TabularInline):
    """Used inside SubjectAdmin to show which years this subject appears in."""
    model = SubjectYear
    fields = ['school_year', 'teachers']
    autocomplete_fields = ['school_year']
    filter_horizontal = ['teachers']
    extra = 0
    verbose_name = _('Ročník')
    verbose_name_plural = _('Ročníky, kde se předmět vyučuje')


# ---------------------------------------------------------------------------
# Model admins
# ---------------------------------------------------------------------------

@admin.register(SchoolYear)
class SchoolYearAdmin(ModelAdmin):
    list_display = ['name', 'is_active', 'subject_count', 'created_by', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SubjectYearInline]

    @admin.display(description=_('Předmětů'))
    def subject_count(self, obj):
        return obj.subjects.count()


@admin.register(Subject)
class SubjectAdmin(ModelAdmin):
    list_display = ['name', 'slug', 'year_count', 'material_count']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SubjectYearsInline]

    @admin.display(description=_('Ročníků'))
    def year_count(self, obj):
        return obj.years.count()

    @admin.display(description=_('Materiálů'))
    def material_count(self, obj):
        return Material.objects.filter(subject__subject=obj).count()


@admin.register(SubjectYear)
class SubjectYearAdmin(ModelAdmin):
    list_display = ['subject', 'school_year', 'classroom_link_display']
    list_filter = ['school_year']
    search_fields = ['subject__name', 'school_year__name']
    autocomplete_fields = ['subject', 'school_year']
    filter_horizontal = ['teachers']
    inlines = [SubjectVIPInline, MaterialInline]
    fields = ['subject', 'school_year', 'teachers', 'classroom_link']

    @admin.display(description=_('Classroom'))
    def classroom_link_display(self, obj):
        if obj.classroom_link:
            return '✓'
        return '–'


@admin.register(MaterialType)
class MaterialTypeAdmin(ModelAdmin):
    list_display = ['name', 'slug', 'order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ['name', 'slug', 'material_count']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description=_('Počet materiálů'))
    def material_count(self, obj):
        return obj.materials.count()


@admin.register(Material)
class MaterialAdmin(ModelAdmin):
    form = MaterialAdminForm
    list_display = ['title', 'subject', 'material_type', 'author', 'is_published', 'ocr_processed', 'created_at']
    list_filter = ['material_type', 'is_published', 'ocr_processed', 'subject__school_year', 'tags']
    search_fields = ['title', 'description', 'extracted_text']
    readonly_fields = ['extracted_text', 'ocr_processed', 'created_at', 'updated_at']
    filter_horizontal = ['tags']
    fieldsets = (
        (None, {'fields': ('title', 'icon', 'subject', 'material_type', 'file', 'external_url', 'description', 'tags')}),
        (_('Autor a čas'), {'fields': ('author', 'created_at', 'updated_at', 'is_published')}),
        (_('AI / OCR'), {
            'fields': ('ocr_processed', 'extracted_text'),
            'classes': ('collapse',),
            'description': _('Pole extrahovaný text je pouze pro čtení – vyplňuje se automaticky.'),
        }),
    )
    actions = ['export_csv', 'export_xlsx', 'export_zip']

    @admin.action(description=_('Exportovat jako CSV'))
    def export_csv(self, request, queryset):
        return _export_csv('materialy.csv', MATERIAL_HEADERS, _material_rows(queryset))

    @admin.action(description=_('Exportovat jako Excel (.xlsx)'))
    def export_xlsx(self, request, queryset):
        return _export_xlsx('materialy.xlsx', MATERIAL_HEADERS, _material_rows(queryset))

    @admin.action(description=_('Exportovat soubory jako ZIP'))
    def export_zip(self, request, queryset):
        buf = io.BytesIO()
        count = 0
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for mat in queryset:
                if not mat.file:
                    continue
                try:
                    ext = os.path.splitext(mat.file.name)[1]
                    safe_name = f'{mat.pk}_{slugify(mat.title)}{ext}'
                    with mat.file.open('rb') as f:
                        zf.writestr(safe_name, f.read())
                    count += 1
                except Exception:
                    pass
        buf.seek(0)
        self.message_user(request, f'ZIP obsahuje {count} souborů.')
        response = HttpResponse(buf.read(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="materialy.zip"'
        return response


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ['material', 'author', 'created_at', 'is_visible']
    list_filter = ['is_visible']
    search_fields = ['text', 'author__email', 'material__title']
    readonly_fields = ['material', 'author', 'created_at']
    actions = ['hide_comments']

    @admin.action(description='Skrýt vybrané komentáře')
    def hide_comments(self, request, queryset):
        queryset.update(is_visible=False)


@admin.register(SubjectVIP)
class SubjectVIPAdmin(ModelAdmin):
    list_display = ['user', 'subject', 'granted_by', 'granted_at']
    list_filter = ['subject__school_year', 'subject']
    search_fields = ['user__email', 'user__username', 'subject__subject__name']
    autocomplete_fields = ['user', 'subject']
    readonly_fields = ['granted_at']


class ZeroResultsFilter(admin.SimpleListFilter):
    title = _('Výsledky')
    parameter_name = 'zero'

    def lookups(self, request, model_admin):
        return [('1', _('Bez výsledků'))]

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(results_count=0)
        return queryset


@admin.register(SearchLog)
class SearchLogAdmin(ModelAdmin):
    list_display = ['timestamp', 'query', 'user', 'results_count', 'zero_results_badge', 'duration_ms', 'year_filter', 'subject_filter']
    list_filter = [ZeroResultsFilter, 'year_filter', 'subject_filter']
    search_fields = ['query', 'user__email', 'user__username']
    readonly_fields = ['query', 'user', 'results_count', 'year_filter', 'subject_filter', 'timestamp', 'duration_ms', 'clicked_result_id']
    date_hierarchy = 'timestamp'
    actions = ['export_csv']

    @admin.display(description='∅', boolean=False)
    def zero_results_badge(self, obj):
        if obj.results_count == 0:
            return '✗'
        return ''

    @admin.action(description=_('Exportovat jako CSV'))
    def export_csv(self, request, queryset):
        headers = ['Čas', 'Dotaz', 'Uživatel', 'Výsledky', 'Doba (ms)', 'Filtr ročník', 'Filtr předmět']
        rows = [
            [
                s.timestamp.strftime('%Y-%m-%d %H:%M'),
                s.query,
                s.user.email if s.user else '',
                s.results_count,
                s.duration_ms or '',
                s.year_filter,
                s.subject_filter,
            ]
            for s in queryset.select_related('user')
        ]
        return _export_csv('search_log.csv', headers, rows)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
