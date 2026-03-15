import csv
import io
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import User


USER_HEADERS = ['ID', 'Email', 'Username', 'Jméno', 'Příjmení', 'Role', 'Aktivní', 'Datum registrace', 'Rok nástupu', 'Materiálů']


def _user_rows(qs):
    qs = qs.annotate(material_count=Count('materials', distinct=True))
    rows = []
    for u in qs:
        rows.append([
            u.pk, u.email, u.username, u.first_name, u.last_name,
            u.get_role_display(), u.is_active,
            u.date_joined.strftime('%Y-%m-%d'),
            u.enrollment_year or '',
            u.material_count,
        ])
    return rows


def _export_csv(filename, headers, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
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


@admin.register(User)
class UserAdmin(ModelAdmin, BaseUserAdmin):
    list_display = ['email', 'username', 'get_full_name', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff']
    list_filter_sheet = True
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['-date_joined']

    fieldsets = BaseUserAdmin.fieldsets + (
        (_('EduBase'), {
            'fields': ('role', 'privacy_level', 'enrollment_year', 'avatar'),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_('EduBase'), {
            'fields': ('email', 'role'),
        }),
    )
    actions = ['export_csv', 'export_xlsx', 'set_role_student', 'set_role_teacher', 'set_role_admin']

    @admin.action(description=_('Exportovat jako CSV'))
    def export_csv(self, request, queryset):
        return _export_csv('uzivatele.csv', USER_HEADERS, _user_rows(queryset))

    @admin.action(description=_('Exportovat jako Excel (.xlsx)'))
    def export_xlsx(self, request, queryset):
        return _export_xlsx('uzivatele.xlsx', USER_HEADERS, _user_rows(queryset))

    @admin.action(description=_('Změnit roli na: Student'))
    def set_role_student(self, request, queryset):
        updated = queryset.update(role=User.Role.STUDENT)
        self.message_user(request, f'Role změněna na Student u {updated} uživatelů.')

    @admin.action(description=_('Změnit roli na: Učitel'))
    def set_role_teacher(self, request, queryset):
        updated = queryset.update(role=User.Role.TEACHER)
        self.message_user(request, f'Role změněna na Učitel u {updated} uživatelů.')

    @admin.action(description=_('Změnit roli na: Admin'))
    def set_role_admin(self, request, queryset):
        updated = queryset.update(role=User.Role.ADMIN)
        self.message_user(request, f'Role změněna na Admin u {updated} uživatelů.')
