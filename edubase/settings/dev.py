from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = ['https://edubase.tech']

# Cloudflare Tunnel terminates TLS – tell Django the real scheme
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-not-for-production')

# django-browser-reload for Tailwind HMR
INSTALLED_APPS += ['django_browser_reload']
MIDDLEWARE += ['django_browser_reload.middleware.BrowserReloadMiddleware']
