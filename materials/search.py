"""
Full-text search over materials.

Czech is a highly inflected language – PostgreSQL FTS word-boundary matching
misses inflected forms (e.g. "fáze" won't hit "fázemi").
Primary strategy: icontains (substring) across title, description, extracted_text.
Results are ordered: title matches first, then by recency.
"""

import html as html_module
import logging
import re
import time
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, Count, IntegerField, Q, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import ListView

from .models import Material, SearchLog

logger = logging.getLogger(__name__)

MAX_RESULTS = 50
MIN_QUERY_LENGTH = 2
LOG_COOLDOWN_MINUTES = 5  # don't log same query from same user within this window
EXCERPT_WINDOW = 200       # chars of context around the first match


# ---------------------------------------------------------------------------
# Excerpt / highlight helpers
# ---------------------------------------------------------------------------

def _make_excerpt(text: str, query: str) -> str:
    """Return an HTML-safe excerpt with query terms wrapped in <mark>."""
    if not text:
        return ''
    lower_text = text.lower()
    lower_query = query.lower()
    pos = lower_text.find(lower_query)
    if pos == -1:
        snippet = text[:EXCERPT_WINDOW].strip()
        prefix = suffix = ''
    else:
        start = max(0, pos - 80)
        end = min(len(text), pos + len(query) + 120)
        snippet = text[start:end].strip()
        prefix = '…' if start > 0 else ''
        suffix = '…' if end < len(text) else ''

    safe = html_module.escape(snippet)
    escaped_query = re.escape(html_module.escape(query))
    highlighted = re.sub(
        escaped_query,
        lambda m: f'<mark class="bg-yellow-200 rounded px-0.5">{m.group()}</mark>',
        safe,
        flags=re.IGNORECASE,
    )
    return mark_safe(f'{prefix}{highlighted}{suffix}')


def _hit_count(material: Material, query: str) -> int:
    """Count how many times query appears across title + description + extracted_text."""
    combined = f'{material.title} {material.description} {material.extracted_text}'.lower()
    return combined.count(query.lower())


# ---------------------------------------------------------------------------
# Search view
# ---------------------------------------------------------------------------

class MaterialSearchView(LoginRequiredMixin, ListView):
    template_name = 'materials/search_results.html'
    context_object_name = 'results'
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip().lstrip('/').strip()
        if len(query) < MIN_QUERY_LENGTH:
            return Material.objects.none()

        base_qs = (
            Material.objects
            .filter(is_published=True)
            .select_related('subject__school_year', 'material_type', 'author')
        )

        year_slug = self.request.GET.get('year', '')
        if year_slug:
            base_qs = base_qs.filter(subject__school_year__slug=year_slug)

        subject_slug = self.request.GET.get('subject', '')
        if subject_slug:
            base_qs = base_qs.filter(subject__subject__slug=subject_slug)

        return (
            base_qs
            .filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(extracted_text__icontains=query)
            )
            .annotate(
                # Title match → show first
                title_match=Case(
                    When(title__icontains=query, then=2),
                    When(description__icontains=query, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            )
            .order_by('-title_match', '-created_at')
            [:MAX_RESULTS]
        )

    def get_context_data(self, **kwargs):
        t_start = time.monotonic()
        ctx = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip().lstrip('/').strip()
        year_filter = self.request.GET.get('year', '')
        subject_filter = self.request.GET.get('subject', '')

        ctx['query'] = query
        ctx['year_filter'] = year_filter
        ctx['subject_filter'] = subject_filter

        from .models import SchoolYear, Subject as SubjectDef
        ctx['school_years'] = SchoolYear.objects.filter(is_active=True)
        ctx['all_subjects'] = SubjectDef.objects.order_by('name')

        # Annotate each result with hit_count and excerpt
        if query:
            enriched = []
            for mat in ctx['object_list']:
                mat.hit_count = _hit_count(mat, query)
                mat.excerpt = _make_excerpt(mat.extracted_text or mat.description, query)
                enriched.append(mat)
            ctx['object_list'] = enriched

        duration_ms = int((time.monotonic() - t_start) * 1000)
        ctx['duration_ms'] = duration_ms

        # Log the search (only when a real query was submitted and user hasn't opted out)
        if query and len(query) >= MIN_QUERY_LENGTH:
            results_count = len(ctx['object_list'])
            if not getattr(self.request.user, 'search_tracking_opt_out', False):
                try:
                    cooldown_cutoff = timezone.now() - timedelta(minutes=LOG_COOLDOWN_MINUTES)
                    already_logged = SearchLog.objects.filter(
                        user=self.request.user,
                        query__iexact=query,
                        timestamp__gte=cooldown_cutoff,
                    ).exists()
                    if not already_logged:
                        SearchLog.objects.create(
                            query=query,
                            user=self.request.user,
                            results_count=results_count,
                            year_filter=year_filter,
                            subject_filter=subject_filter,
                            duration_ms=duration_ms,
                        )
                except Exception:
                    logger.exception('Failed to save search log')

        # Trending searches for empty-state UI
        if not query:
            cutoff = timezone.now() - timedelta(days=30)
            ctx['trending_searches'] = (
                SearchLog.objects
                .filter(timestamp__gte=cutoff, results_count__gt=0)
                .values('query')
                .annotate(cnt=Count('id'))
                .order_by('-cnt')[:8]
            )

        return ctx


# ---------------------------------------------------------------------------
# Click tracking endpoint
# ---------------------------------------------------------------------------

class SearchClickView(LoginRequiredMixin, View):
    """Record which search result the user clicked."""

    def post(self, request):
        material_id = request.POST.get('material_id', '').strip()
        query = request.POST.get('q', '').strip()
        next_url = request.POST.get('next', '/')

        if material_id.isdigit() and query:
            try:
                log = (
                    SearchLog.objects
                    .filter(user=request.user, query__iexact=query)
                    .order_by('-timestamp')
                    .first()
                )
                if log and not log.clicked_result_id:
                    SearchLog.objects.filter(pk=log.pk).update(clicked_result_id=int(material_id))
            except Exception:
                logger.exception('Failed to record search click')

        return redirect(next_url)
