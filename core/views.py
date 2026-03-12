import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
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


@login_required
def notifications_list(request):
    """Show user's notifications and mark them all as read."""
    from .models import Notification
    notifications = list(
        Notification.objects.filter(recipient=request.user).order_by('-created_at')[:50]
    )
    # Mark unread as read
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return render(request, 'core/notifications.html', {'notifications': notifications})


@login_required
def teacher_statistics(request):
    """Statistics for teachers (own subjects) and admins (all subjects)."""
    from django.db.models import Count, Sum
    from materials.models import Material, Subject

    user = request.user
    if not (user.is_teacher or user.is_admin_role or user.is_staff):
        raise PermissionDenied

    if user.is_admin_role or user.is_staff:
        subjects = Subject.objects.select_related('school_year').order_by('school_year__name', 'name')
    else:
        subjects = user.taught_subjects.select_related('school_year').order_by('school_year__name', 'name')

    subject_stats = []
    for subject in subjects:
        qs = Material.objects.filter(subject=subject, is_published=True)
        total_count = qs.count()
        total_downloads = qs.aggregate(s=Sum('download_count'))['s'] or 0
        top_materials = list(qs.order_by('-download_count')[:3])
        recent_count = qs.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        subject_stats.append({
            'subject': subject,
            'total_count': total_count,
            'total_downloads': total_downloads,
            'top_materials': top_materials,
            'recent_count': recent_count,
        })

    return render(request, 'core/statistics.html', {
        'subject_stats': subject_stats,
        'is_admin_view': user.is_admin_role or user.is_staff,
    })
