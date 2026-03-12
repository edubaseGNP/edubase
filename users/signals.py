import logging

from allauth.account.signals import user_signed_up
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(user_signed_up)
def on_user_signed_up(sender, request, user, **kwargs):
    """Log new registrations to audit trail."""
    from core.audit import audit_log
    from core.models import AuditLog

    social = kwargs.get('sociallogin') is not None
    logger.info('New user signed up: %s | role: %s | social: %s', user.email, user.role, social)

    audit_log(
        user=user,
        action=AuditLog.Action.REGISTER,
        obj=user,
        description=f'Registrace: {user.email}' + (' (Google)' if social else ''),
        request=request,
    )


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    from core.audit import audit_log
    from core.models import AuditLog

    audit_log(
        user=user,
        action=AuditLog.Action.LOGIN,
        obj=user,
        description=f'Přihlášení: {user.email}',
        request=request,
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    if user is None:
        return
    from core.audit import audit_log
    from core.models import AuditLog

    audit_log(
        user=user,
        action=AuditLog.Action.LOGOUT,
        obj=user,
        description=f'Odhlášení: {user.email}',
        request=request,
    )
