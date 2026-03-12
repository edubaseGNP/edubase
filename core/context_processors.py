from .models import Notification


def notifications(request):
    """Inject unread notification count into every template context."""
    if not request.user.is_authenticated:
        return {}
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return {'unread_notifications_count': count}
