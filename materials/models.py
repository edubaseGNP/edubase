import os

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


def material_upload_path(instance, filename):
    """Organise uploaded files by year/subject."""
    return os.path.join(
        'materials',
        str(instance.subject.school_year_id),
        str(instance.subject_id),
        filename,
    )


class SchoolYear(models.Model):
    """Ročník – e.g. 'Sexta D', 'Prima A'."""

    name = models.CharField(max_length=100, verbose_name=_('Název'))
    slug = models.SlugField(max_length=120, unique=True, verbose_name=_('Slug'))
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivní'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='created_school_years',
        verbose_name=_('Vytvořil'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Vytvořeno'))

    class Meta:
        verbose_name = _('Ročník')
        verbose_name_plural = _('Ročníky')
        ordering = ['name']

    def __str__(self):
        return self.name


class Subject(models.Model):
    """Global subject definition – shared across school years."""

    name = models.CharField(max_length=200, verbose_name=_('Název'))
    slug = models.SlugField(max_length=220, unique=True, verbose_name=_('Slug'))
    description = models.TextField(blank=True, verbose_name=_('Popis'))

    class Meta:
        verbose_name = _('Předmět')
        verbose_name_plural = _('Předměty')
        ordering = ['name']

    def __str__(self):
        return self.name


class SubjectYear(models.Model):
    """A subject as offered in a specific school year."""

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='years',
        verbose_name=_('Předmět'),
    )
    school_year = models.ForeignKey(
        SchoolYear,
        on_delete=models.CASCADE,
        related_name='subjects',
        verbose_name=_('Ročník'),
    )
    teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='taught_subjects',
        limit_choices_to={'role': 'teacher'},
        verbose_name=_('Učitelé'),
    )

    classroom_link = models.URLField(
        blank=True,
        default='',
        max_length=500,
        verbose_name=_('Google Classroom odkaz'),
        help_text=_('Volitelný odkaz na třídu v Google Classroom (vyplní učitel)'),
    )

    class Meta:
        verbose_name = _('Předmět v ročníku')
        verbose_name_plural = _('Předměty v ročnících')
        ordering = ['school_year', 'subject__name']
        unique_together = [('subject', 'school_year')]

    def __str__(self):
        return f'{self.school_year} – {self.subject.name}'

    # Proxy properties – templates using subject.name / subject.slug still work
    @property
    def name(self):
        return self.subject.name

    @property
    def slug(self):
        return self.subject.slug

    @property
    def description(self):
        return self.subject.description


class MaterialType(models.Model):
    """Typ materiálu – e.g. 'Podklady', 'Testy', 'Kontrolní otázky'."""

    name = models.CharField(max_length=100, verbose_name=_('Název'))
    slug = models.SlugField(max_length=120, unique=True, verbose_name=_('Slug'))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Pořadí'))

    class Meta:
        verbose_name = _('Typ materiálu')
        verbose_name_plural = _('Typy materiálů')
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    """Štítek materiálu – e.g. 'maturita', 'opakování', 'domácí úkol'."""

    name = models.CharField(max_length=50, unique=True, verbose_name=_('Název'))
    slug = models.SlugField(max_length=60, unique=True, verbose_name=_('Slug'))

    class Meta:
        verbose_name = _('Štítek')
        verbose_name_plural = _('Štítky')
        ordering = ['name']

    def __str__(self):
        return self.name


class Material(models.Model):
    """Nahraný materiál – PDF, obrázek, Office dokument nebo externí odkaz."""

    title = models.CharField(max_length=300, verbose_name=_('Název'))
    subject = models.ForeignKey(
        SubjectYear,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name=_('Předmět'),
    )
    material_type = models.ForeignKey(
        MaterialType,
        on_delete=models.PROTECT,
        related_name='materials',
        verbose_name=_('Typ'),
    )
    icon = models.CharField(
        max_length=20,
        default='📄',
        verbose_name=_('Ikona'),
        help_text=_('Emoji ikona materiálu'),
    )
    file = models.FileField(
        upload_to=material_upload_path,
        blank=True,
        verbose_name=_('Soubor'),
    )
    external_url = models.URLField(
        blank=True,
        default='',
        max_length=1000,
        verbose_name=_('Externí odkaz'),
        help_text=_('Odkaz na Google Docs, Slides, Sheets apod. (místo souboru)'),
    )
    description = models.TextField(blank=True, verbose_name=_('Popis'))

    # Authorship
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='materials',
        verbose_name=_('Autor'),
    )

    # Timestamps & history
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Nahráno'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Naposledy upraveno'))

    # AI/OCR – extracted plain text for future AI features (V5.0)
    extracted_text = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Extrahovaný text'),
        help_text=_('Automaticky vyplněno při nahrání. Slouží pro AI generování testů (V5.0).'),
    )
    ocr_processed = models.BooleanField(
        default=False,
        verbose_name=_('OCR zpracováno'),
    )

    tags = models.ManyToManyField(
        'Tag',
        blank=True,
        related_name='materials',
        verbose_name=_('Štítky'),
    )

    is_published = models.BooleanField(default=True, verbose_name=_('Zveřejněno'))

    # Download counter
    download_count = models.PositiveIntegerField(default=0, verbose_name=_('Počet stažení'))

    # Versioning
    version = models.PositiveSmallIntegerField(default=1, verbose_name=_('Verze'))
    parent = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='versions',
        verbose_name=_('Původní materiál'),
    )

    class Meta:
        verbose_name = _('Materiál')
        verbose_name_plural = _('Materiály')
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def file_extension(self):
        if not self.filename:
            return ''
        _, ext = os.path.splitext(self.filename)
        return ext.lower()

    @property
    def is_pdf(self):
        return self.file_extension == '.pdf'

    @property
    def is_image(self):
        return self.file_extension in ('.jpg', '.jpeg', '.png', '.gif', '.webp')

    @property
    def is_office(self):
        return self.file_extension in ('.docx', '.pptx', '.xlsx', '.odt', '.ods', '.odp')

    @property
    def is_external(self):
        return bool(self.external_url and not self.file)

    @property
    def is_google_doc(self):
        return 'docs.google.com/document' in self.external_url

    @property
    def is_google_sheet(self):
        return 'docs.google.com/spreadsheets' in self.external_url

    @property
    def is_google_slides(self):
        return 'docs.google.com/presentation' in self.external_url

    @property
    def display_icon(self):
        """Return user-set icon, or auto-detect from file/URL type if still default."""
        if self.icon and self.icon != '📄':
            return self.icon
        # Auto-detect from source type
        if self.is_google_doc:
            return '📝'
        if self.is_google_sheet:
            return '📊'
        if self.is_google_slides:
            return '🎞️'
        if self.is_image:
            return '🖼️'
        ext = self.file_extension
        if ext in ('.docx', '.odt'):
            return '📝'
        if ext in ('.xlsx', '.ods'):
            return '📊'
        if ext in ('.pptx', '.odp'):
            return '🎞️'
        return '📄'

    @property
    def file_type_label(self):
        """Short label for the file type badge."""
        if self.is_google_doc:
            return 'Docs'
        if self.is_google_sheet:
            return 'Sheets'
        if self.is_google_slides:
            return 'Slides'
        if self.external_url:
            return 'Odkaz'
        ext = self.file_extension.lstrip('.')
        return ext.upper() if ext else ''

    @property
    def open_url(self):
        """Primary URL to open/view the material."""
        if self.external_url:
            return self.external_url
        if self.file:
            return self.file.url
        return ''

    @property
    def reading_time(self):
        """Estimated reading time in minutes (200 words/min)."""
        if not self.extracted_text:
            return None
        words = len(self.extracted_text.split())
        return max(1, round(words / 200))


class Comment(models.Model):
    """Komentář k materiálu."""

    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Materiál'),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='comments',
        verbose_name=_('Autor'),
    )
    text = models.TextField(verbose_name=_('Text'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Čas'))
    is_visible = models.BooleanField(default=True, verbose_name=_('Viditelný'))

    class Meta:
        verbose_name = _('Komentář')
        verbose_name_plural = _('Komentáře')
        ordering = ['created_at']

    def __str__(self):
        return f'{self.author} → {self.material}'


class MaterialLike(models.Model):
    """Líbí se mi – jeden uživatel může lajknout každý materiál max 1×."""

    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('Materiál'),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='liked_materials',
        verbose_name=_('Uživatel'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Líbí se mi')
        verbose_name_plural = _('Líbí se mi')
        unique_together = [('material', 'user')]


class SubjectVIP(models.Model):
    """
    Per-subject VIP permission.

    A Teacher or Admin can grant a Student elevated rights (upload/edit) for one subject.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vip_subjects',
        verbose_name=_('Student'),
    )
    subject = models.ForeignKey(
        SubjectYear,
        on_delete=models.CASCADE,
        related_name='vip_users',
        verbose_name=_('Předmět'),
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='vip_grants_given',
        verbose_name=_('Udělil'),
    )
    granted_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Uděleno'))

    class Meta:
        verbose_name = _('VIP oprávnění')
        verbose_name_plural = _('VIP oprávnění')
        unique_together = [('user', 'subject')]

    def __str__(self):
        return f'{self.user} → VIP → {self.subject}'


class SearchLog(models.Model):
    """Log of user search queries for analytics."""

    query = models.CharField(max_length=300, verbose_name=_('Dotaz'), db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='search_logs',
        verbose_name=_('Uživatel'),
    )
    results_count = models.PositiveSmallIntegerField(default=0, verbose_name=_('Počet výsledků'))
    year_filter = models.CharField(max_length=120, blank=True, default='', verbose_name=_('Filtr ročníku'))
    subject_filter = models.CharField(max_length=220, blank=True, default='', verbose_name=_('Filtr předmětu'))
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name=_('Čas'))
    duration_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Doba (ms)'))
    clicked_result_id = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Klik na výsledek'))

    class Meta:
        verbose_name = _('Log vyhledávání')
        verbose_name_plural = _('Logy vyhledávání')
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} – {self.query!r} ({self.results_count})'
