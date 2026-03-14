from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class SiteConfig(models.Model):
    """
    Singleton model storing site-wide configuration set by the setup wizard.
    Access via SiteConfig.get().
    """

    school_name = models.CharField(max_length=200, default='EduBase', verbose_name=_('Název školy'))
    school_domain = models.CharField(max_length=100, default='localhost', verbose_name=_('Doménové jméno'))
    google_allowed_domain = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Povolená Google doména'),
        help_text=_('Např. skola.cz – ponechte prázdné pro povolení všech domén.'),
    )
    setup_complete = models.BooleanField(default=False, verbose_name=_('Nastavení dokončeno'))

    # ---- Email / SMTP ----------------------------------------------------
    email_notifications_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Emailové notifikace zapnuty'),
        help_text=_('Odesílat emaily učitelům při nahrání nového materiálu.'),
    )
    smtp_host = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name=_('SMTP server'),
        help_text=_('Např. smtp.gmail.com'),
    )
    smtp_port = models.PositiveSmallIntegerField(
        default=587,
        verbose_name=_('SMTP port'),
    )
    smtp_use_tls = models.BooleanField(default=True, verbose_name=_('Použít TLS'))
    smtp_username = models.CharField(max_length=200, blank=True, default='', verbose_name=_('SMTP uživatel'))
    smtp_password = models.CharField(max_length=200, blank=True, default='', verbose_name=_('SMTP heslo'))
    default_from_email = models.EmailField(
        blank=True, default='',
        verbose_name=_('Odesílatel (From)'),
        help_text=_('Např. edubase@skola.cz'),
    )

    # ---- AI / OCR -----------------------------------------------------------
    class AIBackend(models.TextChoices):
        NONE       = 'none',       _('Vypnuto – pouze Tesseract')
        GOOGLE     = 'google',     _('Google Gemini Flash (doporučeno)')
        ANTHROPIC  = 'anthropic',  _('Anthropic Claude Haiku')
        OLLAMA     = 'ollama',     _('Ollama – lokálně na serveru (zdarma)')

    ai_backend = models.CharField(
        max_length=20,
        choices=AIBackend.choices,
        default=AIBackend.NONE,
        verbose_name=_('AI backend'),
        help_text=_('Vyberte poskytovatele AI pro Vision OCR a budoucí funkce (shrnutí, testy).'),
    )
    # Google Gemini
    google_ai_api_key = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name=_('Google AI API klíč'),
        help_text=_('Získejte zdarma na aistudio.google.com – free tier: 1 500 req/den.'),
    )
    google_ai_model = models.CharField(
        max_length=100, blank=True, default='gemini-2.5-flash',
        verbose_name=_('Google AI model'),
        help_text=_('Doporučeno: gemini-2.5-flash. Alternativy: gemini-2.5-pro.'),
    )
    # Anthropic
    anthropic_api_key = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name=_('Anthropic API klíč'),
        help_text=_('Prepaid kredit, bez předplatného. ~0.11 Kč/obrázek.'),
    )
    # Ollama (local)
    ollama_base_url = models.CharField(
        max_length=200, blank=True, default='http://ollama:11434',
        verbose_name=_('Ollama URL'),
        help_text=_('URL lokálního Ollama serveru, např. http://ollama:11434'),
    )
    ollama_vision_model = models.CharField(
        max_length=100, blank=True, default='llama3.2-vision',
        verbose_name=_('Ollama Vision model'),
        help_text=_('Doporučeno: llama3.2-vision (11B) nebo llava:7b pro slabší hardware.'),
    )
    ollama_text_model = models.CharField(
        max_length=100, blank=True, default='llama3.1',
        verbose_name=_('Ollama Text model'),
        help_text=_('Pro shrnutí a generování testů, např. llama3.1 nebo gemma3.'),
    )
    # OCR engine settings
    ocr_pdf_dpi = models.PositiveSmallIntegerField(
        default=300,
        verbose_name=_('PDF OCR – DPI'),
        help_text=_('Rozlišení pro převod PDF stránek na obrázky před OCR. Doporučeno: 300.'),
    )
    ocr_lang = models.CharField(
        max_length=50, default='ces+eng',
        verbose_name=_('Tesseract jazyk'),
        help_text=_('Jazykové balíčky pro Tesseract, např. ces+eng nebo ces.'),
    )

    # ---- Upload limits ------------------------------------------------------
    max_upload_mb = models.PositiveSmallIntegerField(
        default=50,
        verbose_name=_('Max. velikost uploadu (MB)'),
        help_text=_('Maximální velikost nahrávaného souboru v megabajtech.'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Konfigurace webu')
        verbose_name_plural = _('Konfigurace webu')

    @classmethod
    def get(cls):
        """Return (or lazily create) the singleton instance."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.school_name


class AuditLog(models.Model):
    """
    Immutable audit trail for all create/update/delete actions.
    Populated via signals and view helpers in Krok 4.
    """

    class Action(models.TextChoices):
        CREATE = 'create', _('Vytvoření')
        UPDATE = 'update', _('Úprava')
        DELETE = 'delete', _('Smazání')
        VIP_GRANT = 'vip_grant', _('Udělení VIP')
        VIP_REVOKE = 'vip_revoke', _('Odebrání VIP')
        UPLOAD = 'upload', _('Nahrání souboru')
        DOWNLOAD = 'download', _('Stažení')
        LOGIN = 'login', _('Přihlášení')
        LOGOUT = 'logout', _('Odhlášení')
        REGISTER = 'register', _('Registrace')
        COMMENT_ADD = 'comment_add', _('Přidání komentáře')
        COMMENT_DELETE = 'comment_delete', _('Smazání komentáře')

    class Level(models.TextChoices):
        INFO = 'info', _('Info')
        WARNING = 'warning', _('Varování')
        ERROR = 'error', _('Chyba')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
        verbose_name=_('Uživatel'),
    )
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        db_index=True,
        verbose_name=_('Akce'),
    )

    # Generic relation – can point to any model
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Typ objektu'),
    )
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('ID objektu'))
    content_object = GenericForeignKey('content_type', 'object_id')

    level = models.CharField(
        max_length=10,
        choices=Level.choices,
        default=Level.INFO,
        db_index=True,
        verbose_name=_('Úroveň'),
    )
    description = models.TextField(blank=True, verbose_name=_('Popis'))
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name=_('Čas'))
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('IP adresa'))

    class Meta:
        verbose_name = _('Záznam auditu')
        verbose_name_plural = _('Záznamy auditu')
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} – {self.action}'


class AICallLog(models.Model):
    """
    Immutable log of every AI/OCR extraction call.
    Created by materials.tasks.extract_text_task after each run.
    """

    timestamp     = models.DateTimeField(auto_now_add=True, db_index=True)
    backend       = models.CharField(
        max_length=20,
        db_index=True,
        verbose_name=_('Backend'),
        help_text=_('google | anthropic | ollama | tesseract | pdfminer | office'),
    )
    # Soft FK – material may be deleted but log survives
    material      = models.ForeignKey(
        'materials.Material',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='ai_logs',
        verbose_name=_('Materiál'),
    )
    success       = models.BooleanField(default=True, verbose_name=_('Úspěch'), db_index=True)
    chars_extracted = models.PositiveIntegerField(default=0, verbose_name=_('Znaky'))
    duration_ms   = models.PositiveIntegerField(default=0, verbose_name=_('Trvání (ms)'))
    error_msg     = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name=_('Chyba'),
    )

    class FileType(models.TextChoices):
        IMAGE    = 'image',    _('Obrázek')
        PDF_TEXT = 'pdf_text', _('PDF (textová vrstva)')
        PDF_OCR  = 'pdf_ocr',  _('PDF (OCR)')
        OFFICE   = 'office',   _('Office dokument')
        UNKNOWN  = 'unknown',  _('Neznámý')

    class Trigger(models.TextChoices):
        UPLOAD    = 'upload',    _('Nahrání')
        REPROCESS = 'reprocess', _('Přepracování')

    file_type   = models.CharField(max_length=10, choices=FileType.choices, default=FileType.UNKNOWN, db_index=True, verbose_name=_('Typ souboru'))
    model_name  = models.CharField(max_length=100, blank=True, default='', verbose_name=_('Model'))
    attempt     = models.PositiveSmallIntegerField(default=1, verbose_name=_('Pokus č.'))
    tokens_used = models.PositiveIntegerField(default=0, verbose_name=_('Tokeny'))
    trigger     = models.CharField(max_length=15, choices=Trigger.choices, default=Trigger.UPLOAD, db_index=True, verbose_name=_('Spuštění'))

    # Cost estimates (CZK per successful call, 2025 pricing)
    _COST_CZK = {
        'google':    0.01,
        'anthropic': 0.11,
        'ollama':    0.0,
        'tesseract': 0.0,
        'pdfminer':  0.0,
        'office':    0.0,
    }

    @property
    def estimated_cost_czk(self) -> float:
        if not self.success:
            return 0.0
        if self.tokens_used > 0:
            # CZK per 1000 tokens (approximate 2025 pricing at 23 CZK/USD)
            rates = {'google': 0.0023, 'anthropic': 0.046}
            rate = rates.get(self.backend)
            if rate:
                return round(self.tokens_used * rate / 1000, 4)
        # Flat rate fallback
        return {'google': 0.01, 'anthropic': 0.11}.get(self.backend, 0.0)

    class Meta:
        verbose_name = _('AI/OCR volání')
        verbose_name_plural = _('AI/OCR volání')
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {self.backend} – {self.chars_extracted} znaků'


class Notification(models.Model):
    """
    In-app notification for a single user.
    Created programmatically; displayed in the navbar bell icon.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Příjemce'),
    )
    verb = models.CharField(max_length=255, verbose_name=_('Zpráva'))
    target_url = models.CharField(max_length=500, blank=True, default='', verbose_name=_('Odkaz'))
    is_read = models.BooleanField(default=False, db_index=True, verbose_name=_('Přečteno'))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name=_('Čas'))

    class Meta:
        verbose_name = _('Notifikace')
        verbose_name_plural = _('Notifikace')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient} – {self.verb[:60]}'
