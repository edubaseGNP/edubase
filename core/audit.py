"""
Audit log helpers – call these from views and signals to record actions.
"""

import logging

from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str | None:
    """Extract real client IP, respecting X-Forwarded-For."""
    if request is None:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def audit_log(user, action: str, obj=None, description: str = '', request=None, level: str = 'info') -> None:
    """
    Create an AuditLog entry.

    Usage:
        from core.audit import audit_log
        from core.models import AuditLog

        audit_log(request.user, AuditLog.Action.CREATE, material,
                  description=f'Nahráno: {material.title}', request=request)
    """
    from core.models import AuditLog

    try:
        content_type = ContentType.objects.get_for_model(obj) if obj is not None else None
        object_id = obj.pk if obj is not None else None

        AuditLog.objects.create(
            user=user,
            action=action,
            level=level,
            content_type=content_type,
            object_id=object_id,
            description=description,
            ip_address=get_client_ip(request),
        )
    except Exception:
        # Audit log must never crash the main request
        logger.exception('audit_log: failed to write entry (user=%s, action=%s)', user, action)
