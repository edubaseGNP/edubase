import csv
import urllib.request

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import AICallLog, AuditLog, Notification, SiteConfig


def _test_ai_backend(cfg) -> tuple[bool, str]:
    """Quick connectivity / auth test for the configured AI backend."""
    backend = cfg.ai_backend
    try:
        if backend == 'google':
            if not cfg.google_ai_api_key:
                return False, 'API klíč není nastaven'
            from google import genai
            client = genai.Client(api_key=cfg.google_ai_api_key)
            model = cfg.google_ai_model or 'gemini-2.5-flash'
            resp = client.models.generate_content(
                model=model, contents=['Odpověz pouze: OK']
            )
            return True, f'Gemini připojen ({model}) – {resp.text.strip()[:30]}'

        if backend == 'anthropic':
            if not cfg.anthropic_api_key:
                return False, 'API klíč není nastaven'
            import anthropic
            client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
            msg = client.messages.create(
                model='claude-haiku-4-5-20251001', max_tokens=10,
                messages=[{'role': 'user', 'content': 'Odpověz pouze: OK'}],
            )
            return True, f'Claude připojen – {msg.content[0].text.strip()[:30]}'

        if backend == 'ollama':
            url = (cfg.ollama_base_url or 'http://ollama:11434').rstrip('/')
            req = urllib.request.Request(f'{url}/api/tags', method='GET')
            with urllib.request.urlopen(req, timeout=5) as r:
                import json
                data = json.loads(r.read())
            models = [m['name'] for m in data.get('models', [])]
            return True, f'Ollama OK – modely: {", ".join(models[:3]) or "žádné"}'

    except Exception as exc:
        return False, str(exc)[:120]

    return False, 'Neznámý backend'

# Colors for action badges
_ACTION_COLORS = {
    AuditLog.Action.LOGIN:          ('#d1fae5', '#065f46'),  # green
    AuditLog.Action.LOGOUT:         ('#f3f4f6', '#374151'),  # gray
    AuditLog.Action.REGISTER:       ('#dbeafe', '#1e40af'),  # blue
    AuditLog.Action.UPLOAD:         ('#e0e7ff', '#3730a3'),  # indigo
    AuditLog.Action.DOWNLOAD:       ('#ede9fe', '#5b21b6'),  # purple
    AuditLog.Action.CREATE:         ('#dcfce7', '#166534'),  # green dark
    AuditLog.Action.UPDATE:         ('#fef9c3', '#713f12'),  # yellow
    AuditLog.Action.DELETE:         ('#fee2e2', '#991b1b'),  # red
    AuditLog.Action.COMMENT_ADD:    ('#cffafe', '#155e75'),  # cyan
    AuditLog.Action.COMMENT_DELETE: ('#fde8d8', '#9a3412'),  # orange
    AuditLog.Action.VIP_GRANT:      ('#fef3c7', '#92400e'),  # amber
    AuditLog.Action.VIP_REVOKE:     ('#fee2e2', '#7f1d1d'),  # red dark
}

_LEVEL_COLORS = {
    AuditLog.Level.INFO:    ('#f3f4f6', '#374151'),
    AuditLog.Level.WARNING: ('#fef9c3', '#713f12'),
    AuditLog.Level.ERROR:   ('#fee2e2', '#991b1b'),
}


@admin.register(SiteConfig)
class SiteConfigAdmin(ModelAdmin):
    fieldsets = (
        (_('Škola'), {'fields': ('school_name', 'school_domain')}),
        (_('Google OAuth'), {'fields': ('google_allowed_domain',)}),
        (_('Emailové notifikace'), {
            'fields': (
                'email_notifications_enabled',
                'smtp_host', 'smtp_port', 'smtp_use_tls',
                'smtp_username', 'smtp_password',
                'default_from_email',
            ),
            'description': _(
                'Nastavte SMTP server pro odesílání emailů učitelům. '
                'Heslo je uloženo v čistém textu – doporučujeme App Password.'
            ),
        }),
        (_('🤖 AI backend'), {
            'fields': (
                'ai_backend',
                'ai_status',
                'google_ai_api_key',
                'google_ai_model',
                'anthropic_api_key',
                'ollama_base_url', 'ollama_vision_model', 'ollama_text_model',
            ),
            'description': _(
                'Vyberte AI backend pro Vision OCR (obrázky, naskenovaná PDF) a budoucí funkce. '
                'Nastavení se projeví okamžitě – není třeba restartovat server.'
            ),
        }),
        (_('⚙️ OCR Tesseract'), {
            'fields': ('ocr_pdf_dpi', 'ocr_lang'),
            'description': _(
                'Tesseract se vždy použije jako záloha, i když je AI backend zapnutý.'
            ),
        }),
        (_('📁 Nahrávání souborů'), {
            'fields': ('max_upload_mb',),
        }),
        (_('Stav'), {'fields': ('setup_complete', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('created_at', 'updated_at', 'ai_status')

    @admin.display(description=_('Stav připojení'))
    def ai_status(self, obj):
        backend = obj.ai_backend
        if backend == 'none':
            return format_html(
                '<span style="color:#6b7280">⚪ Vypnuto – používá se Tesseract</span>'
            )
        ok, msg = _test_ai_backend(obj)
        if ok:
            return format_html('<span style="color:#16a34a">✅ {}</span>', msg)
        return format_html('<span style="color:#dc2626">❌ {}</span>', msg)

    class Media:
        js = ('admin/js/ai_settings_toggle.js',)

    def has_add_permission(self, request):
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class AuditLogHasIPFilter(admin.SimpleListFilter):
    title = _('IP adresa')
    parameter_name = 'has_ip'

    def lookups(self, request, model_admin):
        return [('yes', _('S IP adresou')), ('no', _('Bez IP adresy'))]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(ip_address__isnull=True).exclude(ip_address='')
        if self.value() == 'no':
            return queryset.filter(ip_address__isnull=True) | queryset.filter(ip_address='')
        return queryset


class AuditLogUserRoleFilter(admin.SimpleListFilter):
    title = _('Role uživatele')
    parameter_name = 'user_role'

    def lookups(self, request, model_admin):
        from users.models import User
        return User.ROLE_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__role=self.value())
        return queryset


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = [
        'timestamp', 'action_badge', 'level_badge', 'user_with_role',
        'object_link', 'short_description', 'ip_address',
    ]
    list_filter = ['action', 'level', 'content_type', AuditLogUserRoleFilter, AuditLogHasIPFilter]
    list_filter_sheet = True
    search_fields = ['user__email', 'user__username', 'description', 'ip_address']
    readonly_fields = [
        'user', 'action', 'level', 'content_type', 'object_id',
        'object_link', 'description', 'timestamp', 'ip_address',
    ]
    date_hierarchy = 'timestamp'
    actions = ['export_csv']

    @admin.display(description=_('Akce'), ordering='action')
    def action_badge(self, obj):
        bg, fg = _ACTION_COLORS.get(obj.action, ('#f3f4f6', '#374151'))
        label = obj.get_action_display()
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:12px;'
            'font-size:0.75rem;font-weight:600;white-space:nowrap">{}</span>',
            bg, fg, label,
        )

    @admin.display(description=_('Uživatel'), ordering='user__email')
    def user_with_role(self, obj):
        if not obj.user:
            return format_html('<span style="color:#9ca3af">—</span>')
        role = obj.user.get_role_display() if hasattr(obj.user, 'get_role_display') else ''
        url = reverse('admin:users_user_change', args=[obj.user_id])
        return format_html(
            '<a href="{}" style="font-weight:500">{}</a>'
            '<br><span style="font-size:.7rem;color:#6b7280">{}</span>',
            url, obj.user.email, role,
        )

    @admin.display(description=_('Úroveň'), ordering='level')
    def level_badge(self, obj):
        bg, fg = _LEVEL_COLORS.get(obj.level, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:12px;'
            'font-size:0.75rem;font-weight:600">{}</span>',
            bg, fg, obj.get_level_display(),
        )

    @admin.display(description=_('Objekt'))
    def object_link(self, obj):
        if obj.content_type is None or obj.object_id is None:
            return '—'
        label = f'{obj.content_type.model} #{obj.object_id}'
        try:
            url = reverse(
                f'admin:{obj.content_type.app_label}_{obj.content_type.model}_change',
                args=[obj.object_id],
            )
            return format_html('<a href="{}">{}</a>', url, label)
        except NoReverseMatch:
            return label

    @admin.display(description=_('Popis'))
    def short_description(self, obj):
        if not obj.description:
            return '—'
        text = obj.description[:80]
        if len(obj.description) > 80:
            text += '…'
        return text

    @admin.action(description=_('Exportovat jako CSV'))
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Čas', 'Akce', 'Úroveň', 'Uživatel', 'Objekt', 'Popis', 'IP adresa'])
        for entry in queryset.select_related('user', 'content_type'):
            writer.writerow([
                entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                entry.get_action_display(),
                entry.get_level_display(),
                entry.user.email if entry.user else '',
                f'{entry.content_type.model} #{entry.object_id}' if entry.content_type else '',
                entry.description,
                entry.ip_address or '',
            ])
        return response

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


_BACKEND_COLORS = {
    'google':    ('#dbeafe', '#1e40af'),
    'anthropic': ('#ede9fe', '#5b21b6'),
    'ollama':    ('#dcfce7', '#166534'),
    'tesseract': ('#f3f4f6', '#374151'),
    'pdfminer':  ('#fef9c3', '#713f12'),
    'office':    ('#cffafe', '#155e75'),
}

_COST_CZK = {
    'google':    0.01,
    'anthropic': 0.11,
}


_FILE_TYPE_COLORS = {
    'image':    ('#fde8d8', '#9a3412'),
    'pdf_text': ('#dcfce7', '#166534'),
    'pdf_ocr':  ('#fef9c3', '#713f12'),
    'office':   ('#dbeafe', '#1e40af'),
    'unknown':  ('#f3f4f6', '#374151'),
}


class AICallLogSchoolYearFilter(admin.SimpleListFilter):
    title = _('Školní ročník')
    parameter_name = 'school_year'

    def lookups(self, request, model_admin):
        from materials.models import SchoolYear
        return [(sy.slug, str(sy)) for sy in SchoolYear.objects.order_by('-name')]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(material__subject__school_year__slug=self.value())
        return queryset


@admin.register(AICallLog)
class AICallLogAdmin(ModelAdmin):
    change_list_template = 'admin/core/aicalllog/change_list.html'

    list_display = [
        'timestamp', 'backend_badge', 'file_type_badge', 'model_name',
        'material_link', 'success_badge', 'attempt',
        'chars_extracted', 'duration_ms', 'tokens_used', 'cost_display', 'trigger',
    ]
    list_filter   = ['backend', 'success', 'file_type', 'trigger', AICallLogSchoolYearFilter]
    list_filter_sheet = True
    search_fields = ['material__title']
    readonly_fields = [
        'timestamp', 'backend', 'material', 'success',
        'chars_extracted', 'duration_ms', 'error_msg',
        'file_type', 'model_name', 'attempt', 'tokens_used', 'trigger',
    ]
    date_hierarchy = 'timestamp'
    actions = ['export_csv']

    def changelist_view(self, request, extra_context=None):
        import datetime
        from django.db.models import Avg, Case, FloatField, Sum, Value, When
        from django.utils import timezone

        today = timezone.now().date()
        qs_today = AICallLog.objects.filter(timestamp__date=today)
        total_today = qs_today.count()
        success_today = qs_today.filter(success=True).count()

        cost_today = qs_today.filter(success=True).aggregate(
            total=Sum(Case(
                When(backend='google', then=Value(0.01)),
                When(backend='anthropic', then=Value(0.11)),
                default=Value(0.0),
                output_field=FloatField(),
            ))
        )['total'] or 0.0

        avg_duration = qs_today.filter(success=True).aggregate(
            avg=Avg('duration_ms')
        )['avg'] or 0

        extra_context = extra_context or {}
        extra_context['ai_stats'] = {
            'total_today': total_today,
            'success_today': success_today,
            'error_today': total_today - success_today,
            'success_rate': round(success_today / total_today * 100) if total_today else 100,
            'cost_today': round(cost_today, 2),
            'avg_duration_s': round(avg_duration / 1000, 1),
            'total_all': AICallLog.objects.count(),
        }
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description=_('Backend'), ordering='backend')
    def backend_badge(self, obj):
        bg, fg = _BACKEND_COLORS.get(obj.backend, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:12px;'
            'font-size:.75rem;font-weight:600">{}</span>',
            bg, fg, obj.backend,
        )

    @admin.display(description=_('Typ'), ordering='file_type')
    def file_type_badge(self, obj):
        bg, fg = _FILE_TYPE_COLORS.get(obj.file_type, ('#f3f4f6', '#374151'))
        label = obj.get_file_type_display() if hasattr(obj, 'get_file_type_display') else obj.file_type
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:12px;'
            'font-size:.75rem;font-weight:600">{}</span>',
            bg, fg, label,
        )

    @admin.display(description=_('Materiál'))
    def material_link(self, obj):
        if not obj.material_id:
            return '—'
        label = obj.material.title[:50] if obj.material else f'#{obj.material_id}'
        try:
            url = reverse('admin:materials_material_change', args=[obj.material_id])
            return format_html('<a href="{}">{}</a>', url, label)
        except NoReverseMatch:
            return label

    @admin.display(description=_('Výsledek'), ordering='success')
    def success_badge(self, obj):
        if obj.success:
            return format_html('<span style="color:#16a34a;font-weight:600">✅ OK</span>')
        return format_html(
            '<span style="color:#dc2626;font-weight:600" title="{}">❌ Chyba</span>',
            obj.error_msg,
        )

    @admin.display(description=_('Cena (Kč)'))
    def cost_display(self, obj):
        cost = obj.estimated_cost_czk
        return f'{cost:.4f} Kč' if cost else '—'

    @admin.action(description=_('Exportovat jako CSV'))
    def export_csv(self, request, queryset):
        import csv as csv_mod
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="ai_call_log.csv"'
        response.write('\ufeff')
        writer = csv_mod.writer(response)
        writer.writerow([
            'Čas', 'Backend', 'Typ souboru', 'Model', 'Materiál',
            'Úspěch', 'Pokus', 'Znaky', 'Trvání (ms)', 'Tokeny',
            'Cena (Kč)', 'Spuštění', 'Chyba',
        ])
        for entry in queryset.select_related('material'):
            writer.writerow([
                entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                entry.backend,
                entry.file_type,
                entry.model_name,
                entry.material.title if entry.material else '',
                'Ano' if entry.success else 'Ne',
                entry.attempt,
                entry.chars_extracted,
                entry.duration_ms,
                entry.tokens_used,
                f'{entry.estimated_cost_czk:.4f}' if entry.estimated_cost_czk else '0',
                entry.trigger,
                entry.error_msg,
            ])
        return response

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ['recipient', 'verb_short', 'target_link', 'read_badge', 'created_at']
    list_filter = ['is_read']
    list_filter_sheet = True
    search_fields = ['recipient__email', 'verb']
    readonly_fields = ['recipient', 'verb', 'target_url', 'is_read', 'created_at']
    date_hierarchy = 'created_at'
    actions = ['mark_read', 'mark_unread', 'delete_selected_notifications']

    @admin.display(description=_('Zpráva'))
    def verb_short(self, obj):
        return obj.verb[:80] + ('…' if len(obj.verb) > 80 else '')

    @admin.display(description=_('Odkaz'))
    def target_link(self, obj):
        if not obj.target_url:
            return '—'
        return format_html('<a href="{}" target="_blank">↗</a>', obj.target_url)

    @admin.display(description=_('Stav'), ordering='is_read')
    def read_badge(self, obj):
        if obj.is_read:
            return format_html('<span style="color:#6b7280;font-size:.8rem">přečteno</span>')
        return format_html('<span style="color:#d97706;font-weight:600;font-size:.8rem">● nové</span>')

    @admin.action(description=_('Označit jako přečtené'))
    def mark_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'Označeno přečtených: {updated}.')

    @admin.action(description=_('Označit jako nepřečtené'))
    def mark_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'Označeno nepřečtených: {updated}.')

    @admin.action(description=_('Smazat vybrané notifikace'))
    def delete_selected_notifications(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Smazáno {count} notifikací.')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
