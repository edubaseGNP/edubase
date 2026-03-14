"""
Celery tasks for materials: OCR text extraction.

Queue routing:
  extract_text_task → ai_ocr queue (concurrency=1, rate_limit='12/m')

Rate limiting strategy:
  1. rate_limit='12/m' on the ai_ocr worker (concurrency=1) → hard cap
  2. 429 / RateLimitError caught → exponential backoff retry
     retry 1: 30 s, retry 2: 60 s, retry 3: 120 s, retry 4: 240 s, retry 5: 480 s
"""

import logging
import time

from celery import shared_task

from .utils import _log_ai_call, _get_ai_cfg, scan_with_clamav

logger = logging.getLogger(__name__)


def _notify_av_infection(material_id: int, title: str, threat: str) -> None:
    """Create an in-app Notification for all staff/admin users about an infected file."""
    try:
        from django.contrib.auth import get_user_model
        from core.models import Notification
        User = get_user_model()
        for admin in User.objects.filter(is_staff=True):
            Notification.objects.create(
                recipient=admin,
                verb=(
                    f'⚠️ Malware detekován a odstraněn: materiál #{material_id} „{title[:60]}" '
                    f'obsahoval hrozbu {threat}.'
                ),
                target_url=f'/admin/materials/material/{material_id}/change/',
            )
    except Exception:
        logger.exception('_notify_av_infection: failed for material %d', material_id)


# AI backends that are subject to external API rate limits
_AI_BACKENDS = {'google', 'anthropic'}

# Exceptions / HTTP codes that signal rate-limit exhaustion
_RATE_LIMIT_MSGS = ('429', 'rate_limit', 'rate limit', 'too many requests', 'quota')


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(kw in msg for kw in _RATE_LIMIT_MSGS)


@shared_task(
    bind=True,
    max_retries=5,
    # rate_limit applies per-worker-process; ai_ocr worker runs concurrency=1
    # → effective global cap is 12 req/min, safely under the 15 RPM free tier
    rate_limit='12/m',
    queue='ai_ocr',
)
def extract_text_task(self, material_id: int, trigger: str = 'upload') -> str:
    """
    Extract text from a Material file and save it to extracted_text.

    - Tesseract / Office: retries up to 5× with default 60 s delay on failure.
    - AI backend (Google/Anthropic): exponential backoff on 429.
    - Never blocks the web request – material is visible immediately after upload.
    """
    from .models import Material
    from .utils import extract_text_from_image, extract_text_from_pdf, extract_text_from_office

    try:
        material = Material.objects.get(pk=material_id)
    except Material.DoesNotExist:
        logger.warning('extract_text_task: Material %d not found – skipping', material_id)
        return 'not_found'

    if not material.file:
        logger.warning('extract_text_task: Material %d has no file', material_id)
        return 'no_file'

    t0 = time.monotonic()
    try:
        filepath = material.file.path

        # ------------------------------------------------------------------
        # Step 1: ClamAV antivirus scan (before OCR / before file is used)
        # ------------------------------------------------------------------
        is_clean, threat = scan_with_clamav(filepath)
        if not is_clean:
            logger.error(
                'extract_text_task: INFECTED file in Material %d – %s – removing',
                material_id, threat,
            )
            # Delete the physical file and unpublish
            material.file.delete(save=False)
            Material.objects.filter(pk=material_id).update(
                file='',
                is_published=False,
                av_status='infected',
                ocr_processed=True,
            )
            _notify_av_infection(material_id, material.title, threat)
            return f'infected:{threat}'

        # Mark as clean (or skipped if ClamAV unavailable)
        av = 'clean' if threat == '' else 'skipped'
        Material.objects.filter(pk=material_id).update(av_status=av)

        # ------------------------------------------------------------------
        # Step 2: OCR / text extraction
        # ------------------------------------------------------------------
        if material.is_pdf:
            result = extract_text_from_pdf(filepath)
        elif material.is_image:
            result = extract_text_from_image(filepath)
        elif material.is_office:
            result = extract_text_from_office(filepath)
        else:
            logger.info('extract_text_task: unsupported type for Material %d', material_id)
            result = None

        duration_ms = int((time.monotonic() - t0) * 1000)

        if result is not None:
            _log_ai_call(
                backend=result.backend_used or 'none',
                material_id=material_id,
                success=True,
                chars=len(result.text),
                duration_ms=duration_ms,
                model_name=result.model_name,
                tokens_used=result.tokens_used,
                file_type=result.file_type,
                attempt=self.request.retries + 1,
                trigger=trigger,
            )
            text = result.text
        else:
            text = ''

        Material.objects.filter(pk=material_id).update(
            extracted_text=text,
            ocr_processed=True,
        )
        logger.info(
            'extract_text_task: Material %d done, %d chars in %dms',
            material_id, len(text), duration_ms,
        )
        return f'ok:{len(text)}'

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        _log_ai_call(
            backend='error',
            material_id=material_id,
            success=False,
            chars=0,
            duration_ms=duration_ms,
            error=str(exc),
            attempt=self.request.retries + 1,
            trigger=trigger,
        )
        if _is_rate_limit_error(exc):
            countdown = 30 * (2 ** self.request.retries)
            logger.warning(
                'extract_text_task: rate limit hit for Material %d (attempt %d) – retrying in %ds',
                material_id, self.request.retries + 1, countdown,
            )
            raise self.retry(exc=exc, countdown=countdown)

        logger.exception('extract_text_task: error processing Material %d', material_id)
        raise self.retry(exc=exc, countdown=60)
