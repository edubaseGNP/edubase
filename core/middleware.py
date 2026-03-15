"""
Custom security middleware for EduBase.
Adds HTTP security headers not covered by Django's built-in SecurityMiddleware.
"""


class SecurityHeadersMiddleware:
    """
    Adds Permissions-Policy, X-DNS-Prefetch-Control and a basic Content-Security-Policy.

    CSP is intentionally permissive regarding inline scripts/styles because the project
    uses django-tailwind inline styles and several inline <script> blocks in templates.
    It still blocks the highest-risk vectors: object embeds, external base tags and
    cross-origin frame embedding (clickjacking).
    """

    # Frontend CSP – no eval needed
    _CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'self';"
    )

    # Admin CSP – unsafe-eval required by Alpine.js v3 (uses new Function() for directives)
    _CSP_ADMIN = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'self';"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        response['X-DNS-Prefetch-Control'] = 'off'
        if 'Content-Security-Policy' not in response:
            csp = self._CSP_ADMIN if request.path.startswith('/admin/') else self._CSP
            response['Content-Security-Policy'] = csp
        return response
