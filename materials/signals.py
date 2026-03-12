"""
Signals for materials app.

- Trigger OCR task when a new Material is created.
- Audit log for SubjectVIP grants/revocations.
"""

import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from core.models import AuditLog

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Track file changes to avoid re-OCR on unrelated saves
# -----------------------------------------------------------------------
_MATERIAL_OLD_FILE: dict[int, str] = {}


@receiver(pre_save, sender='materials.Material')
def track_material_file_change(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            _MATERIAL_OLD_FILE[instance.pk] = old.file.name if old.file else ''
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='materials.Material')
def on_material_save(sender, instance, created, **kwargs):
    from .tasks import extract_text_task

    # Trigger OCR for new materials or when the file changed
    old_file = _MATERIAL_OLD_FILE.pop(instance.pk, None)
    file_changed = created or (old_file is not None and old_file != (instance.file.name if instance.file else ''))

    if file_changed and instance.file:
        logger.info('Scheduling OCR for Material %d (%s)', instance.pk, instance.title)
        extract_text_task.delay(instance.pk)

    # Audit log + email notification
    if created:
        try:
            from core.audit import audit_log
            audit_log(
                user=instance.author,
                action=AuditLog.Action.UPLOAD,
                obj=instance,
                description=f'Nahráno: {instance.title}',
            )
        except Exception:
            logger.exception('Failed to write audit log for Material %d', instance.pk)

        # Notify teachers of this subject by email (background, never raises)
        try:
            _notify_teachers_new_material(instance)
        except Exception:
            logger.exception('Failed to send teacher notification for Material %d', instance.pk)


def _notify_teachers_new_material(material):
    """Send email to all teachers of the subject using SiteConfig SMTP settings."""
    from core.models import SiteConfig
    from django.core.mail import get_connection, EmailMessage

    cfg = SiteConfig.get()
    if not cfg.email_notifications_enabled:
        return
    if not cfg.smtp_host:
        logger.warning('Email notifications enabled but smtp_host not set – skipping')
        return

    teachers = list(material.subject.teachers.exclude(email='').values_list('email', flat=True))
    if not teachers:
        return

    from_email = cfg.default_from_email or cfg.smtp_username or 'edubase@localhost'
    site_domain = cfg.school_domain or 'edubase.tech'
    subject_line = f'[EduBase] Nový materiál: {material.title}'
    body = (
        f'V předmětu {material.subject} byl nahrán nový materiál.\n\n'
        f'Název: {material.title}\n'
        f'Autor: {material.author}\n'
        f'Typ: {material.material_type}\n\n'
        f'Zobrazit: https://{site_domain}/materialy/material/{material.pk}/\n'
    )

    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=cfg.smtp_host,
        port=cfg.smtp_port,
        username=cfg.smtp_username,
        password=cfg.smtp_password,
        use_tls=cfg.smtp_use_tls,
        fail_silently=True,
    )
    msg = EmailMessage(
        subject=subject_line,
        body=body,
        from_email=from_email,
        to=teachers,
        connection=connection,
    )
    msg.send(fail_silently=True)


@receiver(post_delete, sender='materials.Material')
def on_material_delete(sender, instance, **kwargs):
    """Log deletion. The actual file cleanup happens via storage."""
    logger.info('Material deleted: %d – %s', instance.pk, instance.title)

    # Delete the file from storage
    if instance.file:
        try:
            instance.file.storage.delete(instance.file.name)
        except Exception:
            logger.exception('Could not delete file for Material %d', instance.pk)

    try:
        from core.audit import audit_log
        audit_log(
            user=None,
            action=AuditLog.Action.DELETE,
            description=f'Smazán materiál: {instance.title} (ID {instance.pk})',
            level='warning',
        )
    except Exception:
        logger.exception('Failed to write DELETE audit log for Material %d', instance.pk)


# -----------------------------------------------------------------------
# VIP grants
# -----------------------------------------------------------------------

@receiver(post_save, sender='materials.SubjectVIP')
def on_vip_grant(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from core.audit import audit_log
        audit_log(
            user=instance.granted_by,
            action=AuditLog.Action.VIP_GRANT,
            obj=instance.subject,
            description=(
                f'VIP uděleno: {instance.user} → {instance.subject}'
            ),
        )
    except Exception:
        logger.exception('Failed to write VIP grant audit log')


@receiver(post_delete, sender='materials.SubjectVIP')
def on_vip_revoke(sender, instance, **kwargs):
    logger.info('VIP revoked: %s → %s', instance.user, instance.subject)
    try:
        from core.audit import audit_log
        audit_log(
            user=instance.user,
            action=AuditLog.Action.VIP_REVOKE,
            obj=instance.subject,
            description=f'VIP odebráno: {instance.user} ← {instance.subject}',
            level='warning',
        )
    except Exception:
        logger.exception('Failed to write VIP_REVOKE audit log')
