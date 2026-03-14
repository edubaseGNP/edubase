import logging.handlers
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

DJANGO_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.postgres',  # full-text search
]

THIRD_PARTY_APPS = [
    'axes',
    'tailwind',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

LOCAL_APPS = [
    'theme',
    'core',
    'users',
    'materials',
    'setup',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

TAILWIND_APP_NAME = 'theme'
INTERNAL_IPS = ['127.0.0.1']
NPM_BIN_PATH = config('NPM_BIN_PATH', default='npm')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'setup.middleware.SetupMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'edubase.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'core.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'edubase.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='edubase'),
        'USER': config('DB_USER', default='edubase'),
        'PASSWORD': config('DB_PASSWORD', default='edubase_secret'),
        'HOST': config('DB_HOST', default='db'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'cs'
LANGUAGES = [
    ('cs', 'Čeština'),
    ('en', 'English'),
    ('de', 'Deutsch'),
]
TIME_ZONE = 'Europe/Prague'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = [BASE_DIR / 'locale']

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = config('REDIS_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 min hard limit per task

# Queues: 'default' for general tasks, 'ai_ocr' for AI API calls
# ai_ocr worker runs with concurrency=1 + rate_limit to respect 15 RPM API limits
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_ROUTES = {
    'materials.tasks.extract_text_task': {'queue': 'ai_ocr'},
}
CELERY_TASK_QUEUES_MAX_PRIORITY = 10

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'weekly-digest': {
        'task': 'core.tasks.send_weekly_digest',
        'schedule': crontab(hour=8, minute=0, day_of_week='monday'),
    },
    'daily-db-backup': {
        'task': 'core.tasks.backup_database',
        'schedule': crontab(hour=2, minute=30),   # 02:30 every day
    },
}

# ---------------------------------------------------------------------------
# File upload settings
# ---------------------------------------------------------------------------
MATERIAL_MAX_UPLOAD_MB = config('MATERIAL_MAX_UPLOAD_MB', default=50, cast=int)
MATERIAL_ALLOWED_TYPES = [
    'application/pdf',
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    # MS Office
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',   # .docx
    'application/vnd.openxmlformats-officedocument.presentationml.presentation', # .pptx
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',         # .xlsx
    # LibreOffice / ODF
    'application/vnd.oasis.opendocument.text',         # .odt
    'application/vnd.oasis.opendocument.spreadsheet',  # .ods
    'application/vnd.oasis.opendocument.presentation', # .odp
]
IMAGE_COMPRESS_MAX_WIDTH = 1920
IMAGE_COMPRESS_QUALITY = 85

# ---------------------------------------------------------------------------
# OCR / AI settings
# ---------------------------------------------------------------------------
OCR_PDF_DPI = config('OCR_PDF_DPI', default=300, cast=int)
OCR_LANG    = config('OCR_LANG', default='ces+eng')

# AI backend for Vision OCR + future AI features (summary, quiz, …)
# Options: 'none' | 'anthropic' | 'google' | 'ollama'
AI_BACKEND        = config('AI_BACKEND', default='none')
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
GOOGLE_AI_API_KEY = config('GOOGLE_AI_API_KEY', default='')
# Ollama: URL of locally running Ollama server (e.g. http://localhost:11434)
OLLAMA_BASE_URL   = config('OLLAMA_BASE_URL', default='http://ollama:11434')
OLLAMA_VISION_MODEL = config('OLLAMA_VISION_MODEL', default='llama3.2-vision')
OLLAMA_TEXT_MODEL   = config('OLLAMA_TEXT_MODEL',   default='llama3.1')

# Django Allauth
SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ---------------------------------------------------------------------------
# django-axes – brute-force login protection
# ---------------------------------------------------------------------------
AXES_FAILURE_LIMIT = 5           # lock after 5 failed attempts
AXES_COOLOFF_TIME = 0.5          # unlock after 30 minutes (in hours)
AXES_RESET_ON_SUCCESS = True     # reset counter on successful login
AXES_LOCKOUT_PARAMETERS = ['ip_address']   # lock per IP
AXES_ENABLED = True
AXES_VERBOSE = False
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = 'none'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Optional: restrict sign-up to a specific school domain (e.g. 'skola.cz')
GOOGLE_ALLOWED_DOMAIN = config('GOOGLE_ALLOWED_DOMAIN', default='')

SOCIALACCOUNT_ADAPTER = 'users.adapters.EduBaseSocialAccountAdapter'
SOCIALACCOUNT_AUTO_SIGNUP = True
# Skip the intermediate "Are you sure you want to sign in?" page
SOCIALACCOUNT_LOGIN_ON_GET = True
# Connect Google to an existing account if the email already exists
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='EduBase <noreply@edubase.tech>')

# ---------------------------------------------------------------------------
# django-unfold admin theme
# ---------------------------------------------------------------------------
UNFOLD = {
    'SITE_TITLE': 'EduBase',
    'SITE_HEADER': 'EduBase Administrace',
    'DASHBOARD_CALLBACK': 'core.admin_dashboard.dashboard_callback',
    'SITE_URL': '/',
    'SITE_ICON': None,
    'SITE_SYMBOL': 'school',
    'SHOW_HISTORY': True,
    'SHOW_VIEW_ON_SITE': True,
    'COLORS': {
        'primary': {
            '50':  '239 246 255',
            '100': '219 234 254',
            '200': '191 219 254',
            '300': '147 197 253',
            '400': '96 165 250',
            '500': '59 130 246',
            '600': '37 99 235',
            '700': '29 78 216',
            '800': '30 64 175',
            '900': '30 58 138',
            '950': '23 37 84',
        },
    },
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': True,
        'navigation': [
            {
                'title': 'Obsah',
                'separator': False,
                'items': [
                    {'title': 'Školní ročníky', 'icon': 'calendar_today', 'link': '/admin/materials/schoolyear/'},
                    {'title': 'Předměty', 'icon': 'class', 'link': '/admin/materials/subject/'},
                    {'title': 'Předměty v ročnících', 'icon': 'school', 'link': '/admin/materials/subjectyear/'},
                    {'title': 'Typy materiálů', 'icon': 'category', 'link': '/admin/materials/materialtype/'},
                    {'title': 'Materiály', 'icon': 'description', 'link': '/admin/materials/material/'},
                    {'title': 'Štítky', 'icon': 'label', 'link': '/admin/materials/tag/'},
                    {'title': 'Komentáře', 'icon': 'chat', 'link': '/admin/materials/comment/'},
                    {'title': 'Log vyhledávání', 'icon': 'search', 'link': '/admin/materials/searchlog/'},
                ],
            },
            {
                'title': 'Uživatelé',
                'separator': True,
                'items': [
                    {'title': 'Uživatelé', 'icon': 'people', 'link': '/admin/users/user/'},
                    {'title': 'VIP přístupy', 'icon': 'star', 'link': '/admin/materials/subjectvip/'},
                    {'title': 'Google účty', 'icon': 'account_circle', 'link': '/admin/socialaccount/socialaccount/'},
                ],
            },
            {
                'title': 'Systém',
                'separator': True,
                'items': [
                    {'title': 'Záznamy auditu', 'icon': 'history', 'link': '/admin/core/auditlog/'},
                    {'title': 'AI/OCR log', 'icon': 'smart_toy', 'link': '/admin/core/aicalllog/'},
                    {'title': 'Konfigurace', 'icon': 'settings', 'link': '/admin/core/siteconfig/'},
                    {'title': 'Weby (Sites)', 'icon': 'language', 'link': '/admin/sites/site/'},
                ],
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Sentry error tracking (optional – only activated when SENTRY_DSN is set)
# ---------------------------------------------------------------------------
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.05,   # 5 % of requests – adjust in prod
        send_default_pii=False,    # do NOT send user emails/IPs to Sentry
    )

# ---------------------------------------------------------------------------
# Logging – rotating file logs + console
# ---------------------------------------------------------------------------
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {process:d}: {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'app.log',
            'maxBytes': 10 * 1024 * 1024,   # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'security_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'security.log',
            'maxBytes': 5 * 1024 * 1024,    # 5 MB
            'backupCount': 10,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'materials': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'users': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'axes': {
            'handlers': ['console', 'security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'ratelimit': {
            'handlers': ['console', 'security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'OAUTH_PKCE_ENABLED': True,
    }
}
