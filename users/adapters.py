import logging

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class EduBaseSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for Google OAuth.

    - Optionally restricts sign-up to a specific school domain.
    - Assigns default Student role on first sign-up (role default is on the model).
    """

    def is_open_for_signup(self, request, sociallogin):
        # Prefer DB-stored domain (set during setup wizard) over env var
        try:
            from core.models import SiteConfig
            allowed_domain = SiteConfig.get().google_allowed_domain.strip()
        except Exception:
            allowed_domain = getattr(settings, 'GOOGLE_ALLOWED_DOMAIN', '').strip()
        if allowed_domain:
            email = sociallogin.account.extra_data.get('email', '')
            if not email.lower().endswith(f'@{allowed_domain.lower()}'):
                logger.warning(
                    'Sign-up blocked for %s – not in allowed domain @%s',
                    email,
                    allowed_domain,
                )
                from django.contrib import messages
                messages.error(
                    request,
                    _('Přihlášení je povoleno pouze pro doménu @%(domain)s.')
                    % {'domain': allowed_domain},
                )
                return False
        return True

    def populate_user(self, request, sociallogin, data):
        """Populate user fields from Google profile data."""
        user = super().populate_user(request, sociallogin, data)
        # Role defaults to Student (set in model default – no action needed)
        return user
