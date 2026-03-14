"""
Transparent Fernet field encryption for sensitive model fields.

Usage:
    from core.encrypted_fields import EncryptedCharField

    class MyModel(models.Model):
        secret = EncryptedCharField(max_length=200, blank=True, default='')

Configuration (settings / .env):
    FERNET_KEYS = ['base64-key-here']   # list – first key encrypts, all decrypt (key rotation)

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If FERNET_KEYS is empty or not configured, values are stored as plain text (dev fallback).
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models


class EncryptedCharField(models.TextField):
    """
    A TextField that transparently encrypts values at rest using Fernet symmetric encryption.

    - Encryption happens in get_prep_value() (on write to DB)
    - Decryption happens in from_db_value() (on read from DB)
    - Django admin renders it as a normal text input – UX is unchanged
    - Encrypted values are ~3× longer; DB column is TEXT (no length limit)
    """

    def _get_fernet(self):
        keys = getattr(settings, 'FERNET_KEYS', [])
        if isinstance(keys, str):
            keys = [keys]
        keys = [k for k in keys if k]
        if not keys:
            return None
        return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])

    # ------------------------------------------------------------------
    # Read path: DB → Python
    # ------------------------------------------------------------------

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        f = self._get_fernet()
        if f is None:
            return value
        try:
            return f.decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            # Legacy plain-text value (stored before encryption was enabled)
            return value

    def to_python(self, value):
        # Called during deserialization / form validation – value is already plain text
        return value

    # ------------------------------------------------------------------
    # Write path: Python → DB
    # ------------------------------------------------------------------

    def get_prep_value(self, value):
        if not value:
            return value
        f = self._get_fernet()
        if f is None:
            return value
        return f.encrypt(value.encode()).decode()

    # ------------------------------------------------------------------
    # Admin / form rendering – use single-line TextInput like a CharField
    # ------------------------------------------------------------------

    def formfield(self, **kwargs):
        from django import forms
        kwargs.setdefault('widget', forms.TextInput)
        return super().formfield(**kwargs)
