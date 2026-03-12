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
    """Předmět patřící do Ročníku – e.g. 'Český jazyk'."""

    name = models.CharField(max_length=200, verbose_name=_('Název'))
    slug = models.SlugField(max_length=220, verbose_name=_('Slug'))
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
    description = models.TextField(blank=True, verbose_name=_('Popis'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Vytvořeno'))

    class Meta:
        verbose_name = _('Předmět')
        verbose_name_plural = _('Předměty')
        ordering = ['school_year', 'name']
        unique_together = [('school_year', 'slug')]

    def __str__(self):
        return f'{self.school_year} – {self.name}'


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
    """Nahraný materiál – PDF nebo obrázek."""

    title = models.CharField(max_length=300, verbose_name=_('Název'))
    subject = models.ForeignKey(
        Subject,
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
    file = models.FileField(
        upload_to=material_upload_path,
        verbose_name=_('Soubor'),
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
        _, ext = os.path.splitext(self.filename)
        return ext.lower()

    @property
    def is_pdf(self):
        return self.file_extension == '.pdf'

    @property
    def is_image(self):
        return self.file_extension in ('.jpg', '.jpeg', '.png', '.gif', '.webp')

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
        Subject,
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
