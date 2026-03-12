import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

MAX_FAVORITE_SUBJECTS = 4
RECENT_MATERIALS_PER_SUBJECT = 3


def homepage(request):
    """
    Landing page.
    - Anonymous: marketing page.
    - Authenticated with favorites: personalised dashboard.
    - Authenticated without favorites: prompt to choose subjects.
    """
    if not request.user.is_authenticated:
        return render(request, 'core/homepage_anon.html')

    user = request.user
    favorites = list(
        user.favorite_subjects
        .filter(school_year__is_active=True)
        .select_related('school_year')
        .prefetch_related('materials__author', 'materials__material_type')
    )

    # Build per-subject recent materials
    subject_blocks = []
    for subject in favorites:
        recent = list(
            subject.materials
            .filter(is_published=True)
            .select_related('author', 'material_type')
            .order_by('-created_at')[:RECENT_MATERIALS_PER_SUBJECT]
        )
        subject_blocks.append({'subject': subject, 'recent': recent})

    ctx = {
        'subject_blocks': subject_blocks,
        'has_favorites': bool(favorites),
        'max_favorites': MAX_FAVORITE_SUBJECTS,
    }

    if user.is_admin_role or user.is_staff:
        from django.contrib.auth import get_user_model
        from materials.models import Material, SchoolYear, Subject
        from .models import AuditLog
        U = get_user_model()
        ctx['admin_stats'] = {
            'users': U.objects.count(),
            'materials': Material.objects.count(),
            'subjects': Subject.objects.count(),
            'school_years': SchoolYear.objects.filter(is_active=True).count(),
        }
        ctx['recent_logs'] = AuditLog.objects.select_related('user').order_by('-timestamp')[:8]

    return render(request, 'core/homepage.html', ctx)


@login_required
def subject_preferences(request):
    """Let the user pick up to 4 favourite subjects."""
    from materials.models import SchoolYear

    user = request.user
    school_years = (
        SchoolYear.objects
        .filter(is_active=True)
        .prefetch_related('subjects')
        .order_by('name')
    )
    current_ids = set(user.favorite_subjects.values_list('id', flat=True))

    if request.method == 'POST':
        selected_ids = request.POST.getlist('subjects')
        # Enforce maximum
        selected_ids = selected_ids[:MAX_FAVORITE_SUBJECTS]
        user.favorite_subjects.set(selected_ids)
        messages.success(request, _('Oblíbené předměty byly uloženy.'))
        return redirect('core:homepage')

    return render(request, 'core/subject_preferences.html', {
        'school_years': school_years,
        'current_ids': current_ids,
        'max_favorites': MAX_FAVORITE_SUBJECTS,
    })
