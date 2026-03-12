from django.shortcuts import redirect
from django.urls import reverse


class SetupMiddleware:
    """
    Redirect to the setup wizard when setup has not been completed yet.
    Allows access to /setup/* and static/media files unconditionally.
    """

    EXEMPT_PREFIXES = ('/setup/', '/static/', '/media/', '/__debug__/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Always allow access to setup URLs and assets
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        # Check setup status (lazy import to avoid app-registry issues)
        try:
            from core.models import SiteConfig
            cfg = SiteConfig.get()
            if not cfg.setup_complete:
                return redirect(reverse('setup:welcome'))
        except Exception:
            # DB not ready yet (e.g. first migrate) – let the request through
            pass

        return self.get_response(request)
