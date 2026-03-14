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

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        response['X-DNS-Prefetch-Control'] = 'off'
        if 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = self._CSP
        return response
