from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom User model for EduBase.

    Roles: Student (default), Teacher, Admin.
    VIP per-subject permissions are handled in Krok 3 via SubjectVIP model.
    """

    class Role(models.TextChoices):
        STUDENT = 'student', _('Student')
        TEACHER = 'teacher', _('Učitel')
        ADMIN = 'admin', _('Administrátor')

    class PrivacyLevel(models.TextChoices):
        FULL_NAME = 'full_name', _('Celé jméno')
        INITIALS = 'initials', _('Iniciály')
        ANONYMOUS = 'anonymous', _('Anonymně')

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        verbose_name=_('Role'),
        db_index=True,
    )
    privacy_level = models.CharField(
        max_length=20,
        choices=PrivacyLevel.choices,
        default=PrivacyLevel.FULL_NAME,
        verbose_name=_('Zobrazení identity'),
    )
    enrollment_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Rok nástupu'),
        help_text=_('Zobrazuje se při anonymním režimu zobrazení.'),
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        verbose_name=_('Profilový obrázek'),
    )
    # Student homepage: up to 4 pinned subjects for quick access
    favorite_subjects = models.ManyToManyField(
        'materials.SubjectYear',
        blank=True,
        related_name='favorited_by',
        verbose_name=_('Oblíbené předměty'),
    )

    class Meta:
        verbose_name = _('Uživatel')
        verbose_name_plural = _('Uživatelé')

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    @property
    def is_teacher(self) -> bool:
        return self.role == self.Role.TEACHER

    @property
    def is_admin_role(self) -> bool:
        """True for Admin role OR Django superusers."""
        return self.role == self.Role.ADMIN or self.is_superuser

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def get_display_name(self) -> str:
        """Returns name formatted according to the user's privacy_level."""
        if self.privacy_level == self.PrivacyLevel.FULL_NAME:
            return self.get_full_name() or self.username

        if self.privacy_level == self.PrivacyLevel.INITIALS:
            full = self.get_full_name()
            if full:
                return ''.join(part[0].upper() + '.' for part in full.split())
            return self.username[0].upper() + '.'

        # ANONYMOUS
        year = f' ({self.enrollment_year})' if self.enrollment_year else ''
        return str(_('Anonymní')) + year

    def can_upload_to(self, subject) -> bool:
        """True if the user may upload/edit materials for the given subject."""
        if self.is_admin_role or self.is_teacher:
            return True
        # VIP Student: check per-subject permission
        return self.vip_subjects.filter(subject=subject).exists()

    def __str__(self) -> str:
        return self.email or self.username
