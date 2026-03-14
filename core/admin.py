import csv
import urllib.request

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import AuditLog, Notification, SiteConfig


def _test_ai_backend(cfg) -> tuple[bool, str]:
    """Quick connectivity / auth test for the configured AI backend."""
    backend = cfg.ai_backend
    try:
        if backend == 'google':
            if not cfg.google_ai_api_key:
                return False, 'API klíč není nastaven'
            from google import genai
            client = genai.Client(api_key=cfg.google_ai_api_key)
            # Minimal text request to verify key
            resp = client.models.generate_content(
                model='gemini-2.0-flash', contents=['Odpověz pouze: OK']
            )
            return True, f'Gemini připojen – {resp.text.strip()[:30]}'

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


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = [
        'timestamp', 'action_badge', 'level_badge', 'user',
        'object_link', 'short_description', 'ip_address',
    ]
    list_filter = ['action', 'level', 'content_type']
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


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ['recipient', 'verb_short', 'is_read', 'created_at']
    list_filter = ['is_read']
    search_fields = ['recipient__email', 'verb']
    readonly_fields = ['recipient', 'verb', 'target_url', 'is_read', 'created_at']
    date_hierarchy = 'created_at'
    actions = ['mark_read', 'mark_unread']

    @admin.display(description=_('Zpráva'))
    def verb_short(self, obj):
        return obj.verb[:80] + ('…' if len(obj.verb) > 80 else '')

    @admin.action(description=_('Označit jako přečtené'))
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description=_('Označit jako nepřečtené'))
    def mark_unread(self, request, queryset):
        queryset.update(is_read=False)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
