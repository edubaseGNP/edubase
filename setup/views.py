from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.sites.models import Site
from django.shortcuts import redirect, render
from django.urls import reverse

from core.models import SiteConfig
from .forms import AdminAccountForm, SchoolConfigForm

User = get_user_model()

# Session keys
_SCHOOL_KEY = 'setup_school_data'

SETUP_STEPS = [(1, 'Vítejte'), (2, 'Škola'), (3, 'Účet'), (4, 'Hotovo')]


def _setup_allowed(request):
    """Return True when the wizard may be accessed (setup not yet done)."""
    try:
        return not SiteConfig.get().setup_complete
    except Exception:
        return True


def welcome(request):
    """Step 1 – Welcome screen with basic system checks."""
    if not _setup_allowed(request):
        return redirect('/')

    checks = _run_system_checks()
    return render(request, 'setup/step_welcome.html', {'checks': checks, 'step': 1, 'setup_steps': SETUP_STEPS})


def school(request):
    """Step 2 – School name & Google OAuth credentials."""
    if not _setup_allowed(request):
        return redirect('/')

    initial = request.session.get(_SCHOOL_KEY, {})
    if request.method == 'POST':
        form = SchoolConfigForm(request.POST)
        if form.is_valid():
            request.session[_SCHOOL_KEY] = form.cleaned_data
            return redirect(reverse('setup:admin_account'))
    else:
        form = SchoolConfigForm(initial=initial)

    return render(request, 'setup/step_school.html', {'form': form, 'step': 2, 'setup_steps': SETUP_STEPS})


def admin_account(request):
    """Step 3 – Create superuser account."""
    if not _setup_allowed(request):
        return redirect('/')

    if _SCHOOL_KEY not in request.session:
        return redirect(reverse('setup:school'))

    if request.method == 'POST':
        form = AdminAccountForm(request.POST)
        if form.is_valid():
            _finalize_setup(request, form.cleaned_data)
            return redirect(reverse('setup:done'))
    else:
        form = AdminAccountForm()

    return render(request, 'setup/step_admin.html', {'form': form, 'step': 3, 'setup_steps': SETUP_STEPS})


def done(request):
    """Step 4 – Setup complete."""
    try:
        cfg = SiteConfig.get()
        if not cfg.setup_complete:
            return redirect(reverse('setup:welcome'))
    except Exception:
        return redirect(reverse('setup:welcome'))

    return render(request, 'setup/step_done.html', {'step': 4, 'school_name': cfg.school_name, 'setup_steps': SETUP_STEPS})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finalize_setup(request, admin_data):
    school_data = request.session.get(_SCHOOL_KEY, {})

    # 1. Save SiteConfig
    cfg = SiteConfig.get()
    cfg.school_name = school_data.get('school_name', 'EduBase')
    cfg.school_domain = school_data.get('school_domain', 'localhost')
    cfg.google_allowed_domain = school_data.get('google_allowed_domain', '')
    cfg.setup_complete = True
    cfg.save()

    # 2. Update django.contrib.sites
    try:
        site = Site.objects.get(pk=1)
        site.domain = cfg.school_domain
        site.name = cfg.school_name
        site.save()
    except Site.DoesNotExist:
        Site.objects.create(pk=1, domain=cfg.school_domain, name=cfg.school_name)

    # 3. Create/update Google SocialApp
    _upsert_google_app(
        client_id=school_data.get('google_client_id', ''),
        secret=school_data.get('google_client_secret', ''),
    )

    # 4. Create superuser
    user = User.objects.create_superuser(
        username=admin_data['email'].split('@')[0],
        email=admin_data['email'],
        password=admin_data['password1'],
        first_name=admin_data['first_name'],
        last_name=admin_data['last_name'],
        role=User.Role.ADMIN,
    )

    # 5. Clean up session
    request.session.pop(_SCHOOL_KEY, None)

    # 6. Log the admin in automatically
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')


def _upsert_google_app(client_id, secret):
    """Create or update the allauth Google SocialApp linked to site 1."""
    from allauth.socialaccount.models import SocialApp
    from django.contrib.sites.models import Site

    site = Site.objects.get(pk=1)
    app, created = SocialApp.objects.get_or_create(
        provider='google',
        defaults={'name': 'Google', 'client_id': client_id, 'secret': secret},
    )
    if not created:
        app.client_id = client_id
        app.secret = secret
        app.name = 'Google'
        app.save()
    app.sites.add(site)


def _run_system_checks():
    """Return a list of (label, ok, detail) tuples for the welcome screen."""
    import importlib
    checks = []

    # Database
    try:
        from django.db import connection
        connection.ensure_connection()
        checks.append(('Databáze (PostgreSQL)', True, ''))
    except Exception as exc:
        checks.append(('Databáze (PostgreSQL)', False, str(exc)))

    # Redis / Celery broker
    try:
        from django.conf import settings
        import redis
        url = getattr(settings, 'CELERY_BROKER_URL', 'redis://redis:6379/0')
        r = redis.from_url(url, socket_connect_timeout=2)
        r.ping()
        checks.append(('Redis (Celery broker)', True, ''))
    except Exception as exc:
        checks.append(('Redis (Celery broker)', False, str(exc)))

    # Tesseract OCR
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        checks.append(('Tesseract OCR', True, f'verze {version}'))
    except Exception as exc:
        checks.append(('Tesseract OCR', False, str(exc)))

    # poppler / pdf2image
    try:
        from pdf2image.exceptions import PDFInfoNotInstalledError
        import subprocess
        result = subprocess.run(['pdfinfo', '-v'], capture_output=True, timeout=5)
        checks.append(('Poppler (pdf2image)', True, ''))
    except Exception:
        checks.append(('Poppler (pdf2image)', False, 'pdfinfo není dostupný'))

    return checks
