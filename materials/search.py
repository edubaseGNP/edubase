"""
Full-text search over materials.

Czech is a highly inflected language – PostgreSQL FTS word-boundary matching
misses inflected forms (e.g. "fáze" won't hit "fázemi").
Primary strategy: icontains (substring) across title, description, extracted_text.
Results are ordered: title matches first, then by recency.
"""

import logging
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, Count, IntegerField, Q, When
from django.utils import timezone
from django.views.generic import ListView

from .models import Material, SearchLog

logger = logging.getLogger(__name__)

MAX_RESULTS = 50
MIN_QUERY_LENGTH = 2
LOG_COOLDOWN_MINUTES = 5  # don't log same query from same user within this window


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
            base_qs = base_qs.filter(subject__slug=subject_slug)

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
        ctx = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip().lstrip('/').strip()
        year_filter = self.request.GET.get('year', '')
        subject_filter = self.request.GET.get('subject', '')

        ctx['query'] = query
        ctx['year_filter'] = year_filter
        ctx['subject_filter'] = subject_filter

        from .models import SchoolYear, Subject
        ctx['school_years'] = SchoolYear.objects.filter(is_active=True)
        ctx['all_subjects'] = (
            Subject.objects
            .select_related('school_year')
            .order_by('school_year__name', 'name')
        )

        # Log the search (only when a real query was submitted)
        if query and len(query) >= MIN_QUERY_LENGTH:
            results_count = len(ctx['object_list'])
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
