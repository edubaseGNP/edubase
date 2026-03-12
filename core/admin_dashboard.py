"""
Admin dashboard callback – injects statistics and chart data into the admin index.
"""
import json
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def dashboard_callback(request, context):
    if not request.user.is_staff:
        return context

    from django.contrib.auth import get_user_model
    from materials.models import Material, MaterialLike, Comment
    User = get_user_model()

    # ------------------------------------------------------------------
    # Summary cards
    # ------------------------------------------------------------------
    total_users = User.objects.count()
    total_materials = Material.objects.filter(is_published=True).count()
    total_downloads = Material.objects.aggregate(t=Sum('download_count'))['t'] or 0
    total_likes = MaterialLike.objects.count()
    total_comments = Comment.objects.filter(is_visible=True).count()

    context['dashboard_stats'] = [
        {'label': str(_('Uživatelé')),   'value': total_users,     'icon': 'people',       'color': 'blue'},
        {'label': str(_('Materiály')),   'value': total_materials,  'icon': 'description',  'color': 'green'},
        {'label': str(_('Stažení')),     'value': total_downloads,  'icon': 'download',     'color': 'purple'},
        {'label': str(_('Líbí se mi')), 'value': total_likes,      'icon': 'favorite',     'color': 'red'},
        {'label': str(_('Komentáře')),   'value': total_comments,   'icon': 'chat',         'color': 'orange'},
    ]

    # ------------------------------------------------------------------
    # Chart 1: uploads per day – last 30 days
    # ------------------------------------------------------------------
    today = timezone.now().date()
    thirty_ago = today - timedelta(days=29)
    uploads_qs = (
        Material.objects.filter(created_at__date__gte=thirty_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(cnt=Count('id'))
        .order_by('day')
    )
    uploads_by_day = {row['day']: row['cnt'] for row in uploads_qs}
    upload_labels = []
    upload_values = []
    for i in range(30):
        d = thirty_ago + timedelta(days=i)
        upload_labels.append(d.strftime('%-d. %-m.'))
        upload_values.append(uploads_by_day.get(d, 0))

    context['chart_uploads'] = json.dumps({
        'labels': upload_labels,
        'data': upload_values,
    })

    # ------------------------------------------------------------------
    # Chart 2: top subjects by material count
    # ------------------------------------------------------------------
    from materials.models import Subject
    top_subjects = (
        Subject.objects.annotate(mat_count=Count('materials', filter=Q(materials__is_published=True)))
        .order_by('-mat_count')[:10]
    )
    context['chart_subjects'] = json.dumps({
        'labels': [s.name for s in top_subjects],
        'data': [s.mat_count for s in top_subjects],
    })

    # ------------------------------------------------------------------
    # Chart 3: users by role (doughnut)
    # ------------------------------------------------------------------
    role_counts = User.objects.values('role').annotate(cnt=Count('id'))
    role_map = {r['role']: r['cnt'] for r in role_counts}
    context['chart_roles'] = json.dumps({
        'labels': [str(_('Studenti')), str(_('Učitelé')), str(_('Administrátoři'))],
        'data': [role_map.get('student', 0), role_map.get('teacher', 0), role_map.get('admin', 0)],
    })

    # ------------------------------------------------------------------
    # Recent uploads table (last 10)
    # ------------------------------------------------------------------
    context['recent_materials'] = (
        Material.objects.filter(is_published=True)
        .select_related('author', 'subject__school_year', 'material_type')
        .order_by('-created_at')[:10]
    )

    # ------------------------------------------------------------------
    # Top search queries (last 30 days)
    # ------------------------------------------------------------------
    from materials.models import SearchLog
    context['top_searches'] = (
        SearchLog.objects
        .filter(timestamp__gte=timezone.now() - timedelta(days=30))
        .values('query')
        .annotate(cnt=Count('id'), zero_results=Count('id', filter=Q(results_count=0)))
        .order_by('-cnt')[:10]
    )

    # ------------------------------------------------------------------
    # Recent audit events (last 20, warnings/errors highlighted)
    # ------------------------------------------------------------------
    from core.models import AuditLog
    seven_ago = timezone.now() - timedelta(days=7)
    context['audit_warnings'] = AuditLog.objects.filter(
        timestamp__gte=seven_ago,
        level__in=[AuditLog.Level.WARNING, AuditLog.Level.ERROR],
    ).count()
    context['recent_audit'] = (
        AuditLog.objects
        .select_related('user', 'content_type')
        .order_by('-timestamp')[:20]
    )

    return context
