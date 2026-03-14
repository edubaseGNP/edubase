"""
Management command: re-run OCR on existing materials.

Usage:
  # Reprocess only images not yet OCR'd
  python manage.py reprocess_ocr

  # Force reprocess ALL images (overwrite existing extracted_text)
  python manage.py reprocess_ocr --force

  # Use Claude Vision (requires USE_CLAUDE_OCR=true + ANTHROPIC_API_KEY)
  python manage.py reprocess_ocr --use-claude --force

  # Only PDFs
  python manage.py reprocess_ocr --type pdf

  # Dry run – show what would be processed
  python manage.py reprocess_ocr --dry-run
"""

import time

from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = 'Re-run OCR text extraction on existing materials.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Reprocess even materials that already have extracted_text.',
        )
        parser.add_argument(
            '--use-claude', action='store_true',
            help='Override USE_CLAUDE_OCR setting and force Claude Vision for images.',
        )
        parser.add_argument(
            '--type', choices=['image', 'pdf', 'all'], default='all',
            help='Which file types to reprocess (default: all).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would be processed without actually doing it.',
        )
        parser.add_argument(
            '--subject', type=str, default='',
            help='Filter by subject slug (e.g. elektrotechnik).',
        )

    def handle(self, *args, **options):
        from django.conf import settings as _s
        from materials.models import Material
        from materials.utils import (
            extract_text_from_image, extract_text_from_pdf,
            extract_text_from_office, _claude_vision_extract,
        )

        force      = options['force']
        use_claude = options['use_claude']
        file_type  = options['type']
        dry_run    = options['dry_run']
        subject_slug = options['subject']

        # Override Claude setting if --use-claude flag given
        if use_claude:
            _s.USE_CLAUDE_OCR    = True
            if not getattr(_s, 'ANTHROPIC_API_KEY', ''):
                self.stderr.write(self.style.ERROR(
                    'ANTHROPIC_API_KEY is not set – cannot use Claude Vision.'
                ))
                return

        # Build queryset
        qs = Material.objects.filter(is_published=True).exclude(file='')
        if not force:
            qs = qs.filter(Q(ocr_processed=False) | Q(extracted_text=''))
        if subject_slug:
            qs = qs.filter(subject__subject__slug=subject_slug)

        # Filter by type
        IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        PDF_EXT    = {'.pdf'}
        OFFICE_EXTS = {'.docx', '.pptx', '.xlsx', '.odt', '.ods', '.odp'}

        import os

        def _ext(m):
            return os.path.splitext(m.file.name)[1].lower() if m.file else ''

        if file_type == 'image':
            materials = [m for m in qs if _ext(m) in IMAGE_EXTS]
        elif file_type == 'pdf':
            materials = [m for m in qs if _ext(m) in PDF_EXT]
        else:
            materials = list(qs)

        total = len(materials)
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Žádné materiály k přeprocessování.'))
            return

        self.stdout.write(
            f'{"[DRY RUN] " if dry_run else ""}Nalezeno {total} materiálů k přeprocessování '
            f'(force={force}, use_claude={use_claude}, type={file_type}).'
        )

        ok = errors = skipped = 0
        t0 = time.time()

        for i, material in enumerate(materials, 1):
            ext      = _ext(material)
            label    = f'[{i}/{total}] #{material.pk} {material.title[:50]}'

            if dry_run:
                self.stdout.write(f'  {label} ({ext})')
                continue

            try:
                filepath = material.file.path
                if ext in IMAGE_EXTS:
                    text = extract_text_from_image(filepath)
                elif ext in PDF_EXT:
                    text = extract_text_from_pdf(filepath)
                elif ext in OFFICE_EXTS:
                    text = extract_text_from_office(filepath)
                else:
                    self.stdout.write(f'  {label} – přeskočeno (nepodporovaný typ {ext})')
                    skipped += 1
                    continue

                Material.objects.filter(pk=material.pk).update(
                    extracted_text=text,
                    ocr_processed=True,
                )
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ {label} → {len(text)} znaků')
                )
                ok += 1

            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f'  ✗ {label} – chyba: {exc}')
                )
                errors += 1

        elapsed = time.time() - t0
        self.stdout.write(
            self.style.SUCCESS(
                f'\nHotovo za {elapsed:.1f}s: {ok} OK, {errors} chyb, {skipped} přeskočeno.'
            )
        )
