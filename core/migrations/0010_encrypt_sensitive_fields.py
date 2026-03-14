"""
Migration: change smtp_password, google_ai_api_key, anthropic_api_key
to EncryptedCharField (TEXT column) and encrypt any existing values.
"""

from django.db import migrations
import core.encrypted_fields


def encrypt_existing(apps, schema_editor):
    """Encrypt any non-empty, non-encrypted values in the singleton SiteConfig."""
    from django.conf import settings as djsettings
    try:
        from cryptography.fernet import Fernet, MultiFernet
    except ImportError:
        return  # cryptography not installed – skip (no values to encrypt yet)

    keys = getattr(djsettings, 'FERNET_KEYS', [])
    if isinstance(keys, str):
        keys = [keys]
    keys = [k for k in keys if k]
    if not keys:
        return  # No keys configured – leave values as plain text

    f = MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])
    SiteConfig = apps.get_model('core', 'SiteConfig')

    for cfg in SiteConfig.objects.all():
        changed = False
        for fname in ('smtp_password', 'google_ai_api_key', 'anthropic_api_key'):
            val = getattr(cfg, fname, '') or ''
            if val and not val.startswith('gAAAAA'):  # Not already Fernet-encrypted
                setattr(cfg, fname, f.encrypt(val.encode()).decode())
                changed = True
        if changed:
            cfg.save(update_fields=['smtp_password', 'google_ai_api_key', 'anthropic_api_key'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_google_ai_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='siteconfig',
            name='smtp_password',
            field=core.encrypted_fields.EncryptedCharField(
                blank=True, default='', verbose_name='SMTP heslo',
            ),
        ),
        migrations.AlterField(
            model_name='siteconfig',
            name='google_ai_api_key',
            field=core.encrypted_fields.EncryptedCharField(
                blank=True, default='',
                verbose_name='Google AI API klíč',
                help_text='Získejte zdarma na aistudio.google.com – free tier: 1 500 req/den.',
            ),
        ),
        migrations.AlterField(
            model_name='siteconfig',
            name='anthropic_api_key',
            field=core.encrypted_fields.EncryptedCharField(
                blank=True, default='',
                verbose_name='Anthropic API klíč',
                help_text='Prepaid kredit, bez předplatného. ~0.11 Kč/obrázek.',
            ),
        ),
        migrations.RunPython(encrypt_existing, migrations.RunPython.noop),
    ]
