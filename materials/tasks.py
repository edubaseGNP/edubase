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

from celery import shared_task

logger = logging.getLogger(__name__)

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
def extract_text_task(self, material_id: int) -> str:
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

    try:
        filepath = material.file.path

        if material.is_pdf:
            text = extract_text_from_pdf(filepath)
        elif material.is_image:
            text = extract_text_from_image(filepath)
        elif material.is_office:
            text = extract_text_from_office(filepath)
        else:
            logger.info('extract_text_task: unsupported type for Material %d', material_id)
            text = ''

        Material.objects.filter(pk=material_id).update(
            extracted_text=text,
            ocr_processed=True,
        )
        logger.info(
            'extract_text_task: Material %d done, %d chars extracted',
            material_id, len(text),
        )
        return f'ok:{len(text)}'

    except Exception as exc:
        if _is_rate_limit_error(exc):
            # Exponential backoff: 30 s → 60 → 120 → 240 → 480
            countdown = 30 * (2 ** self.request.retries)
            logger.warning(
                'extract_text_task: rate limit hit for Material %d '
                '(attempt %d) – retrying in %ds',
                material_id, self.request.retries + 1, countdown,
            )
            raise self.retry(exc=exc, countdown=countdown)

        logger.exception('extract_text_task: error processing Material %d', material_id)
        raise self.retry(exc=exc, countdown=60)
