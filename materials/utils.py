"""
Utility functions for materials: image compression and OCR text extraction.
"""

import io
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Image compression
# ---------------------------------------------------------------------------

def compress_image_file(file_field, max_width: int = 1920, quality: int = 85) -> None:
    """
    Resize and compress an uploaded image in-place.

    - If width > max_width: downscale proportionally.
    - JPEG output for non-transparent images, PNG otherwise.
    - Replaces the file content on the FieldFile.
    """
    from PIL import Image

    try:
        file_field.seek(0)
        img = Image.open(file_field)
        original_format = img.format or 'JPEG'
        has_alpha = img.mode in ('RGBA', 'LA', 'P')

        # Resize if necessary
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
            logger.debug('Image resized to %dx%d', max_width, new_height)

        output = io.BytesIO()
        if has_alpha:
            img.save(output, format='PNG', optimize=True)
            new_name = _replace_extension(file_field.name, '.png')
        else:
            img.convert('RGB').save(output, format='JPEG', quality=quality, optimize=True)
            new_name = _replace_extension(file_field.name, '.jpg')

        output.seek(0)
        file_field.save(new_name, output, save=False)
        logger.info('Image compressed: %s', new_name)

    except Exception:
        logger.exception('Image compression failed for %s', file_field.name)


def _replace_extension(filename: str, new_ext: str) -> str:
    import os
    base, _ = os.path.splitext(filename)
    return base + new_ext


# ---------------------------------------------------------------------------
# OCR / text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(filepath: str) -> str:
    """
    Extract text from a PDF file.
    1. Try pdfminer (works for text-layer PDFs).
    2. Fallback: convert pages to images with pdf2image and run Tesseract OCR.
    """
    text = _pdfminer_extract(filepath)
    if text.strip():
        logger.debug('pdfminer succeeded for %s (%d chars)', filepath, len(text))
        return text

    logger.debug('pdfminer returned empty text – falling back to OCR for %s', filepath)
    return _pdf_ocr_extract(filepath)


def extract_text_from_image(filepath: str, lang: str = 'ces+eng') -> str:
    """Run Tesseract OCR on an image file."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(filepath)
        text = pytesseract.image_to_string(img, lang=lang)
        logger.debug('Tesseract OCR: %d chars from %s', len(text), filepath)
        return text.strip()
    except Exception:
        logger.exception('Tesseract OCR failed for %s', filepath)
        return ''


def _pdfminer_extract(filepath: str) -> str:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(filepath) or ''
    except Exception:
        logger.exception('pdfminer failed for %s', filepath)
        return ''


def _pdf_ocr_extract(filepath: str, dpi: int = 150, lang: str = 'ces+eng') -> str:
    """Convert PDF pages to images and run Tesseract on each."""
    try:
        import pytesseract
        from pdf2image import convert_from_path

        pages = convert_from_path(filepath, dpi=dpi)
        texts = [pytesseract.image_to_string(page, lang=lang) for page in pages]
        return '\n\n'.join(texts).strip()
    except Exception:
        logger.exception('PDF OCR fallback failed for %s', filepath)
        return ''


# ---------------------------------------------------------------------------
# Office document text extraction
# ---------------------------------------------------------------------------

def extract_text_from_docx(filepath: str) -> str:
    """Extract plain text from a .docx file using python-docx."""
    try:
        from docx import Document
        doc = Document(filepath)
        parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)
        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    parts.append(' | '.join(row_texts))
        return '\n'.join(parts).strip()
    except Exception:
        logger.exception('docx extraction failed for %s', filepath)
        return ''


def extract_text_from_pptx(filepath: str) -> str:
    """Extract plain text from a .pptx file using python-pptx."""
    try:
        from pptx import Presentation
        prs = Presentation(filepath)
        parts = []
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_texts = []
            for shape in slide.shapes:
                if hasattr(shape, 'text') and shape.text.strip():
                    slide_texts.append(shape.text.strip())
            if slide_texts:
                parts.append(f'--- Snímek {slide_num} ---\n' + '\n'.join(slide_texts))
        return '\n\n'.join(parts).strip()
    except Exception:
        logger.exception('pptx extraction failed for %s', filepath)
        return ''


def extract_text_from_xlsx(filepath: str) -> str:
    """Extract cell values from a .xlsx file using openpyxl."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        parts = []
        for sheet in wb.worksheets:
            sheet_parts = [f'=== {sheet.title} ===']
            for row in sheet.iter_rows(values_only=True):
                row_vals = [str(v) for v in row if v is not None and str(v).strip()]
                if row_vals:
                    sheet_parts.append(' | '.join(row_vals))
            if len(sheet_parts) > 1:
                parts.append('\n'.join(sheet_parts))
        wb.close()
        return '\n\n'.join(parts).strip()
    except Exception:
        logger.exception('xlsx extraction failed for %s', filepath)
        return ''


def extract_text_from_odf(filepath: str) -> str:
    """Extract text from ODF files (.odt, .ods, .odp) using odfpy."""
    try:
        from odf.opendocument import load
        from odf import text as odftext
        from odf.teletype import extractText
        doc = load(filepath)
        texts = []
        for elem in doc.body.getElementsByType(odftext.P):
            t = extractText(elem).strip()
            if t:
                texts.append(t)
        return '\n'.join(texts).strip()
    except Exception:
        logger.exception('ODF extraction failed for %s', filepath)
        return ''


def extract_text_from_office(filepath: str) -> str:
    """Dispatch to the correct office extractor based on file extension."""
    import os
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.docx':
        return extract_text_from_docx(filepath)
    if ext == '.pptx':
        return extract_text_from_pptx(filepath)
    if ext == '.xlsx':
        return extract_text_from_xlsx(filepath)
    if ext in ('.odt', '.ods', '.odp'):
        return extract_text_from_odf(filepath)
    return ''
