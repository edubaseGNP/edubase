"""
Periodic Celery tasks for core app.
"""
import gzip
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(queue='default')
def send_weekly_digest() -> str:
    """
    Send weekly email digest to users with email_digest_enabled=True.
    Scheduled via Celery Beat (see settings/base.py CELERY_BEAT_SCHEDULE).
    """
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from django.core.mail import send_mail
    from materials.models import Material

    User = get_user_model()
    week_ago = timezone.now() - timezone.timedelta(days=7)

    try:
        from core.models import SiteConfig
        cfg = SiteConfig.get()
        if not cfg.email_notifications_enabled or not cfg.smtp_host:
            logger.info('send_weekly_digest: email not configured, skipping')
            return 'email_not_configured'
        from_email = cfg.default_from_email or 'noreply@edubase.tech'
    except Exception:
        logger.warning('send_weekly_digest: could not get SiteConfig')
        return 'config_error'

    recipients = User.objects.filter(
        email_digest_enabled=True,
        email__isnull=False,
    ).exclude(email='')

    sent = 0
    for user in recipients:
        try:
            # Get new materials in user's favorite subjects
            fav_subjects = user.favorite_subjects.all()
            if not fav_subjects.exists():
                continue
            new_materials = (
                Material.objects.filter(
                    subject__in=fav_subjects,
                    is_published=True,
                    created_at__gte=week_ago,
                )
                .select_related('author', 'subject__subject')
                .order_by('-created_at')[:20]
            )
            if not new_materials.exists():
                continue

            lines = [f'Dobrý den {user.get_display_name()},\n',
                     'Tento týden přibyly nové materiály ve vašich oblíbených předmětech:\n']
            for m in new_materials:
                lines.append(f'• {m.subject.subject.name}: {m.title} (autor: {m.author.get_display_name() if m.author else "neznámý"})')
            lines.append('\nZobrazte vše na EduBase.')

            send_mail(
                subject='[EduBase] Týdenní přehled nových materiálů',
                message='\n'.join(lines),
                from_email=from_email,
                recipient_list=[user.email],
                fail_silently=True,
            )
            sent += 1
        except Exception:
            logger.exception('send_weekly_digest: failed for user %d', user.pk)

    logger.info('send_weekly_digest: sent to %d users', sent)
    return f'sent:{sent}'


@shared_task(queue='default')
def backup_database() -> str:
    """
    Create a compressed pg_dump of the PostgreSQL database.
    Keeps the last 7 daily backups in /app/backups/.
    Scheduled via Celery Beat (see settings/base.py CELERY_BEAT_SCHEDULE).
    """
    backup_dir = Path(settings.BASE_DIR) / 'backups'
    backup_dir.mkdir(exist_ok=True)

    db = settings.DATABASES['default']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dump_path = backup_dir / f'backup_{timestamp}.sql.gz'

    env = os.environ.copy()
    env['PGPASSWORD'] = db.get('PASSWORD', '')

    try:
        result = subprocess.run(
            [
                'pg_dump',
                '-h', db.get('HOST', 'db'),
                '-p', str(db.get('PORT', '5432')),
                '-U', db.get('USER', 'edubase'),
                db.get('NAME', 'edubase'),
            ],
            env=env,
            capture_output=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors='replace'))

        with gzip.open(dump_path, 'wb') as gz:
            gz.write(result.stdout)

        size_mb = dump_path.stat().st_size / (1024 * 1024)
        logger.info('backup_database: %s created (%.1f MB)', dump_path.name, size_mb)

        # Retain only the 7 most recent backups
        backups = sorted(backup_dir.glob('backup_*.sql.gz'))
        for old in backups[:-7]:
            old.unlink()
            logger.info('backup_database: pruned %s', old.name)

        return f'ok:{dump_path.name}:{size_mb:.1f}MB'

    except Exception as exc:
        logger.error('backup_database: failed – %s', exc)
        if dump_path.exists():
            dump_path.unlink()
        raise
