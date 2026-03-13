"""
Celery tasks for materials: OCR text extraction.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def extract_text_task(self, material_id: int) -> str:
    """
    Extract text from a Material file and save it to extracted_text.

    Retries up to 3 times with 60 s delay on failure.
    """
    from .models import Material
    from .utils import extract_text_from_image, extract_text_from_pdf

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
            from .utils import extract_text_from_office
            text = extract_text_from_office(filepath)
        else:
            logger.info('extract_text_task: unsupported file type for Material %d', material_id)
            text = ''

        Material.objects.filter(pk=material_id).update(
            extracted_text=text,
            ocr_processed=True,
        )
        logger.info(
            'extract_text_task: Material %d processed, %d chars extracted',
            material_id,
            len(text),
        )
        return f'ok:{len(text)}'

    except Exception as exc:
        logger.exception('extract_text_task: error processing Material %d', material_id)
        raise self.retry(exc=exc)
