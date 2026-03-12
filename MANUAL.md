# EduBase – Technický manuál

Kompletní přehled architektury, funkcí a návodů pro vývojáře i administrátory.

---

## Obsah

1. [Architektura](#architektura)
2. [Databázové modely](#databázové-modely)
3. [Role a oprávnění](#role-a-oprávnění)
4. [URL struktura](#url-struktura)
5. [Django aplikace](#django-aplikace)
6. [OCR a zpracování souborů](#ocr-a-zpracování-souborů)
7. [Vyhledávání](#vyhledávání)
8. [Audit log](#audit-log)
9. [Admin dashboard](#admin-dashboard)
10. [Přihlašování a zabezpečení](#přihlašování-a-zabezpečení)
11. [Emaily a notifikace](#emaily-a-notifikace)
12. [i18n – vícejazyčnost](#i18n--vícejazyčnost)
13. [Klávesové zkratky](#klávesové-zkratky)
14. [Administrace – průvodce](#administrace--průvodce)
15. [Roadmap / co zbývá](#roadmap--co-zbývá)

---

## Architektura

```
Browser → Nginx (HTTPS) → Gunicorn (Django) → PostgreSQL
                                            → Redis → Celery worker (OCR)
                                            → Media files (disk)
                                            → Static files (WhiteNoise)
```

### Docker služby

| Služba | Obraz | Účel |
|--------|-------|------|
| `web` | vlastní (Python 3.13 + Tesseract) | Django aplikace |
| `db` | postgres:16-alpine | Databáze |
| `redis` | redis:7-alpine | Broker pro Celery |
| `celery` | vlastní (stejný jako web) | OCR na pozadí |

### Nastavení (settings)

| Soubor | Kdy se použije |
|--------|----------------|
| `edubase/settings/base.py` | Základ – vždy načten |
| `edubase/settings/dev.py` | Vývoj (DEBUG=True) |
| `edubase/settings/prod.py` | Produkce (DEBUG=False) |

`DJANGO_SETTINGS_MODULE` se nastavuje v `docker-compose.yml` nebo `.env`.

---

## Databázové modely

### `users.User` (vlastní user model)

| Pole | Typ | Popis |
|------|-----|-------|
| `email` | EmailField | Primární identifikátor (unikátní) |
| `username` | CharField | Zobrazované jméno |
| `role` | CharField | `student` / `teacher` / `admin` |
| `privacy_level` | CharField | `full_name` / `initials` / `anonymous` |
| `enrollment_year` | PositiveSmallIntegerField | Rok nástupu (pro anon. zobrazení) |
| `favorite_subjects` | M2M → Subject | Oblíbené předměty pro homepage |
| `is_staff` | BooleanField | True pouze pro admin role (Django admin přístup) |

### `materials.SchoolYear`

Ročník školy (např. „Sexta D"). Má `slug` pro URL a příznak `is_active`.

### `materials.Subject`

Předmět patřící do ročníku (např. „Fyzika"). Má `slug`, M2M `teachers` (učitelé přiřazení k předmětu).

### `materials.MaterialType`

Typ materiálu (Podklady, Testy, Kontrolní otázky). Seedováno migrací `0002`.

### `materials.Tag`

Štítek pro materiál (volitelný). M2M vztah přes `Material.tags`.

### `materials.Material`

Hlavní model. Klíčová pole:

| Pole | Popis |
|------|-------|
| `file` | Nahraný soubor (PDF/obrázek) |
| `extracted_text` | Text extrahovaný OCR (pro vyhledávání a budoucí AI) |
| `ocr_processed` | Bool – zda OCR proběhlo |
| `download_count` | Počítadlo stažení |
| `version` | Číslo verze (1, 2, 3…) |
| `previous_version` | FK na předchozí verzi (stromová struktura) |
| `is_published` | Zveřejněno / skryto |

### `materials.Comment`

Komentář k materiálu. Má `is_visible` (soft-delete místo fyzického smazání).

### `materials.MaterialLike`

M2M přes tabulku (user ↔ material), unikátní kombinace.

### `materials.SubjectVIP`

VIP oprávnění studenta pro konkrétní předmět. Umožňuje studentovi nahrávat materiály.

### `materials.SearchLog`

Log každého vyhledávání: dotaz, uživatel, počet výsledků, filtry, čas.

### `core.SiteConfig`

Singleton (vždy jen 1 záznam, pk=1). Konfigurace školy nastavená přes Setup průvodce nebo admin:
- Název školy, doména
- Google OAuth přihlašovací údaje (přes allauth SocialApp)
- SMTP nastavení pro emaily

### `core.AuditLog`

Imutabilní audit trail. Viz sekce [Audit log](#audit-log).

---

## Role a oprávnění

### Přehled rolí

| Role | `is_staff` | Django admin | Nahrávání | VIP udělení |
|------|-----------|-------------|-----------|-------------|
| Student | False | ❌ | ❌ (pokud nemá VIP) | ❌ |
| VIP Student | False | ❌ | ✅ (jen svůj předmět) | ❌ |
| Učitel | False | ❌ | ✅ (všechny předměty) | ✅ |
| Admin | True | ✅ | ✅ | ✅ |

### Klíčové metody na `User`

```python
user.is_student       # bool
user.is_teacher       # bool
user.is_admin_role    # True pro role=admin nebo superuser

user.can_upload_to(subject)
# → True pokud: admin | teacher | VIP pro daný předmět

user.get_display_name()
# → Dle privacy_level: celé jméno / iniciály / "Anonymní (rok)"
```

### Kontrola v šablonách

```django
{% load edubase_tags %}
{% if request.user|can_upload_to:subject %}
  <!-- zobraz tlačítko nahrát -->
{% endif %}
```

### VIP Student

Admin nebo učitel může udělit VIP přístup studentovi ke konkrétnímu předmětu:
- Frontend: tlačítko „Udělit VIP" na stránce předmětu
- Admin: `SubjectVIP` tabulka nebo inline v `SubjectAdmin`

---

## URL struktura

### Veřejné / autentizované

| URL | View | Popis |
|-----|------|-------|
| `/` | `core:homepage` | Homepage (různá dle role) |
| `/materialy/` | `materials:school_year_list` | Seznam ročníků |
| `/materialy/<year>/<subject>/` | `materials:subject_detail` | Detail předmětu |
| `/materialy/<year>/<subject>/nahrat/` | `materials:upload` | Nahrát materiál |
| `/materialy/<year>/<subject>/hromadne/` | `materials:bulk_upload` | Hromadný upload |
| `/materialy/<year>/<subject>/stahnout-zip/` | `materials:subject_zip` | Stáhnout vše jako ZIP |
| `/materialy/material/<pk>/` | `materials:material_detail` | Detail materiálu |
| `/materialy/material/<pk>/stahnout/` | `materials:material_download` | Stáhnout soubor |
| `/materialy/material/<pk>/like/` | `materials:material_like` | Like/unlike (POST) |
| `/materialy/material/<pk>/komentar/` | `materials:comment_add` | Přidat komentář (POST) |
| `/materialy/material/<pk>/nova-verze/` | `materials:material_new_version` | Nahrát novou verzi |
| `/materialy/material/<pk>/smazat/` | `materials:material_delete` | Smazat materiál |
| `/materialy/hledat/?q=dotaz` | `materials:search` | Fulltextové hledání |
| `/uzivatele/profil/<pk>/` | `users:profile` | Profil uživatele |
| `/oblibene/` | `core:subject_preferences` | Výběr oblíbených předmětů |
| `/accounts/...` | allauth | Přihlášení, odhlášení |

### Admin

| URL | Popis |
|-----|-------|
| `/admin/` | Django admin (jen `is_staff`) |
| `/admin/materials/material/` | Správa materiálů |
| `/admin/materials/subject/` | Správa předmětů |
| `/admin/materials/schoolyear/` | Správa ročníků |
| `/admin/materials/searchlog/` | Log vyhledávání |
| `/admin/users/user/` | Správa uživatelů |
| `/admin/core/auditlog/` | Audit log |
| `/admin/core/siteconfig/` | Konfigurace webu |

### Setup průvodce

| URL | Popis |
|-----|-------|
| `/setup/` | Uvítací krok |
| `/setup/skola/` | Nastavení školy + Google OAuth |
| `/setup/admin/` | Vytvoření admin účtu |
| `/setup/hotovo/` | Dokončení |

Průvodce se aktivuje při prvním spuštění (`SiteConfig.setup_complete=False`). Middleware `SetupMiddleware` přesměruje vše na `/setup/` dokud není průvodce dokončen.

---

## Django aplikace

### `core`

- `models.py` – `SiteConfig` (singleton), `AuditLog`
- `views.py` – homepage, subject_preferences
- `audit.py` – helper `audit_log(user, action, obj, description, request, level)`
- `admin_dashboard.py` – callback pro unfold admin dashboard
- `templatetags/edubase_tags.py` – `can_upload_to` filtr

### `users`

- `models.py` – custom `User` model
- `signals.py` – audit log pro login, logout, registraci
- `adapters.py` – allauth adapter (omezení domény Google)
- `views.py` – `UserProfileView`
- `admin.py` – `UserAdmin` s CSV/Excel exportem a bulk změnou rolí

### `materials`

- `models.py` – všechny modely obsahu
- `views.py` – všechny views pro materiály, komentáře, VIP, ZIP
- `search.py` – `MaterialSearchView` (icontains + ranking)
- `forms.py` – `MaterialUploadForm` (validace velikosti a typu)
- `tasks.py` – Celery task `extract_text_task` (OCR)
- `signals.py` – auto-spuštění OCR, audit log, email notifikace
- `utils.py` – komprese obrázků (`compress_image_file`)
- `admin.py` – admin pro všechny modely, exporty CSV/Excel/ZIP

### `setup`

- `views.py` – 4-krokový průvodce instalací
- `middleware.py` – `SetupMiddleware`

---

## OCR a zpracování souborů

### Povolené typy

`application/pdf`, `image/jpeg`, `image/png`, `image/gif`, `image/webp`

Max. velikost: `MATERIAL_MAX_UPLOAD_MB` (default 50 MB).

### Obrázky

Při uploadu se automaticky komprimují na max. šířku `IMAGE_COMPRESS_MAX_WIDTH` (1920 px) a kvalitu `IMAGE_COMPRESS_QUALITY` (85). Implementováno v `materials/utils.py`.

### OCR pipeline

1. Uživatel nahraje soubor → `MaterialUploadForm` validuje
2. `Material` se uloží do DB → signal `post_save` detekuje nový soubor
3. Spustí se Celery task `extract_text_task(material_id)`
4. Task (v `materials/tasks.py`):
   - PDF s textem → `pdfminer.six` extrahuje text přímo
   - PDF skenované / obrázek → `pdf2image` + `pytesseract` (Tesseract s `ces+eng`)
5. Výsledek se uloží do `material.extracted_text`, `ocr_processed=True`

Tesseract jazyky: `ces` (čeština) + `eng` (angličtina).

### Sledování změn souboru

`pre_save` signal ukládá původní název souboru do `_MATERIAL_OLD_FILE`. OCR se spustí jen pokud se soubor skutečně změnil (zabraňuje zbytečnému re-OCR při editaci metadat).

---

## Vyhledávání

### Jak funguje

`MaterialSearchView` (`materials/search.py`) používá **icontains** (substring match) — spolehlivé pro česky skloňovaná slova.

```
/materialy/hledat/?q=dotaz&year=slug-rocniku&subject=slug-predmetu
```

Ranking výsledků (ORDER BY):
1. Shoda v názvu (`title_match=2`)
2. Shoda v popisu (`title_match=1`)
3. Shoda v extrahovaném textu (`title_match=0`)
4. Sekundárně: datum nahrání (nejnovější první)

### Omezení dotazu

- Minimální délka: 2 znaky
- Max. výsledků: 50
- Filtr ročníku a předmětu (kombinovatelné)

### Sanitizace vstupu

```python
query = request.GET.get('q', '').strip().lstrip('/').strip()
```
Odstraní mezery a náhodné lomítko (způsobeno klávesovou zkratkou `/`).

### Search log

Každé vyhledávání (min. 2 znaky) se zaloguje do `SearchLog`. Deduplication: stejný dotaz od stejného uživatele se nezaloguje znovu po dobu 5 minut.

Statistiky dostupné v `/admin/materials/searchlog/` a na admin dashboardu.

---

## Audit log

### Model `core.AuditLog`

| Pole | Popis |
|------|-------|
| `user` | FK na uživatele (nullable – smazaný user) |
| `action` | Typ akce (viz níže) |
| `level` | `info` / `warning` / `error` |
| `content_type` | Na jaký model se akce vztahuje |
| `object_id` | ID objektu |
| `description` | Textový popis |
| `timestamp` | Čas (auto) |
| `ip_address` | IP adresa (z X-Forwarded-For nebo REMOTE_ADDR) |

### Typy akcí

| Kód | Kdy se loguje |
|-----|--------------|
| `login` | Přihlášení uživatele |
| `logout` | Odhlášení |
| `register` | Nová registrace (email nebo Google) |
| `upload` | Nahrání materiálu |
| `download` | Stažení materiálu |
| `update` | Nahrání nové verze materiálu |
| `delete` | Smazání materiálu (level=warning) |
| `comment_add` | Přidání komentáře |
| `comment_delete` | Skrytí komentáře (level=warning) |
| `vip_grant` | Udělení VIP přístupu |
| `vip_revoke` | Odebrání VIP přístupu (level=warning) |
| `create` | Vytvoření objektu (obecné) |

### Zápis z kódu

```python
from core.audit import audit_log
from core.models import AuditLog

audit_log(
    user=request.user,
    action=AuditLog.Action.UPLOAD,
    obj=material,             # volitelné – Generic FK
    description='Nahráno: Fyzika notes.pdf',
    request=request,          # pro IP adresu
    level='info',             # default
)
```

---

## Admin dashboard

`/admin/` – dashboard s těmito sekcemi (implementováno v `core/admin_dashboard.py`):

| Widget | Popis |
|--------|-------|
| **Stat karty** | Uživatelé, Materiály, Stažení, Líbí se, Komentáře |
| **Graf: Nahrávání** | Line chart – počet nahrání za posledních 30 dní |
| **Graf: Role** | Donut chart – počet uživatelů dle role |
| **Graf: Top předměty** | Bar chart – 10 předmětů s nejvíce materiály |
| **Top hledané výrazy** | 10 nejhledanějších dotazů za 30 dní (s počtem nulových výsledků) |
| **Poslední nahrávání** | Tabulka posledních 10 materiálů |
| **Audit log** | Posledních 20 událostí s barevnými odznaky, počet varování za 7 dní |

---

## Přihlašování a zabezpečení

### Google OAuth

Nastaveno přes `django-allauth` + `allauth.socialaccount.providers.google`. Přihlašovací údaje (Client ID, Secret) se ukládají do `SocialApp` přes Setup průvodce.

Volitelné omezení na školní doménu: `GOOGLE_ALLOWED_DOMAIN=skola.cz` v `.env` nebo přes `SiteConfig.google_allowed_domain` v admin.

### Ochrana proti brute force (`django-axes`)

- **Limit**: 5 špatných pokusů → uzamčení IP
- **Cooldown**: 30 minut
- **Reset**: automaticky při úspěšném přihlášení
- **Správa**: `/admin/axes/accessattempt/` – přehled pokusů, ruční odemčení

### HTTPS a produkce

V `prod.py` je připraveno:
- `SECURE_SSL_REDIRECT = True`
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`

---

## Emaily a notifikace

### Konfigurace

Přes Django admin → **Konfigurace** (`/admin/core/siteconfig/`):

| Pole | Popis |
|------|-------|
| Emailové notifikace zapnuty | Master switch |
| SMTP server | Např. `smtp.gmail.com` |
| SMTP port | Default 587 |
| Použít TLS | Doporučeno True |
| SMTP uživatel | Email účet |
| SMTP heslo | App Password (doporučeno) |
| Odesílatel (From) | Zobrazený odesílatel |

### Kdy se posílají emaily

Při nahrání nového materiálu se odesílá email všem učitelům přiřazeným k danému předmětu (`subject.teachers`).

Implementováno v `materials/signals.py` → `_notify_teachers_new_material()`. Pokud SMTP není nakonfigurováno, email se potichu přeskočí.

---

## i18n – vícejazyčnost

Podporované jazyky: **čeština** (výchozí), **angličtina**.

Přepínač jazyka je v navigaci (globus ikona).

### Přidání nových překladů

```bash
# 1. Označit řetězce v kódu: _('text') nebo {% trans "text" %}
# 2. Extrahovat
python manage.py makemessages --locale cs --locale en

# 3. Přeložit v locale/cs/LC_MESSAGES/django.po a locale/en/...

# 4. Zkompilovat
python manage.py compilemessages --locale cs --locale en

# 5. Zkopírovat .mo do containeru a restartovat
docker compose cp locale/cs/LC_MESSAGES/django.mo web:/app/locale/cs/LC_MESSAGES/django.mo
docker compose cp locale/en/LC_MESSAGES/django.mo web:/app/locale/en/LC_MESSAGES/django.mo
docker compose restart web
```

---

## Klávesové zkratky

Implementovány v `templates/base.html`:

| Zkratka | Akce |
|---------|------|
| `/` | Zaostří vyhledávací pole (desktop) |
| `U` | Přejde na stránku nahrávání materiálu |

Poznámka: zkratka `/` také sanitizuje vstup (odstraní náhodné `/` z URL lomaítka).

---

## Administrace – průvodce

### Správa uživatelů `/admin/users/user/`

**Hromadné akce** (zaškrtnout více uživatelů):
- Exportovat jako CSV
- Exportovat jako Excel (.xlsx)
- Změnit roli na: Student / Učitel / Admin

### Správa materiálů `/admin/materials/material/`

**Hromadné akce**:
- Exportovat jako CSV
- Exportovat jako Excel (.xlsx)
- Exportovat soubory jako ZIP

**Filtry**: typ materiálu, zveřejněno, OCR, ročník, štítky

### Log vyhledávání `/admin/materials/searchlog/`

- Filtry: bez výsledků, ročník, předmět
- Export CSV
- Přehled v dashboardu (top 10 dotazů)

### Audit log `/admin/core/auditlog/`

- Barevné odznaky dle typu akce
- Filtr dle úrovně (Info / Varování / Chyba)
- Klikatelné odkazy na objekty
- Export CSV

### Konfigurace `/admin/core/siteconfig/`

Singleton – vždy jen jeden záznam. Nastavení školy, Google OAuth omezení, SMTP.

---

## Roadmap / co zbývá

### Hotovo ✅

- [x] Django projekt + Docker (Tesseract OCR) + PostgreSQL + Tailwind CSS
- [x] Vlastní User model, Google OAuth, RBAC role (Student/Učitel/Admin/VIP)
- [x] Modely: Ročníky, Předměty, Typy materiálů, Materiály, Verze, Komentáře, Liky
- [x] Upload souborů (PDF + obrázky), komprese obrázků, OCR extrakce textu (Celery)
- [x] Frontend: ročníky, předměty, detail materiálu, vyhledávání, profil uživatele
- [x] Oblíbené předměty na homepage, personalizovaný dashboard
- [x] Štítky (tagy) na materiálech s filtrováním
- [x] Admin dashboard s grafy (Chart.js)
- [x] Audit log (12 typů akcí, 3 úrovně závažnosti)
- [x] Log vyhledávání s deduplication a trending výrazy
- [x] Emailové notifikace učitelům (SMTP konfigurovatelné z adminu)
- [x] Hromadné akce v adminu (CSV/Excel/ZIP export, bulk změna rolí)
- [x] Ochrana proti brute force (`django-axes`)
- [x] Stažení předmětu jako ZIP
- [x] Klávesové zkratky (`/` pro hledání, `U` pro upload)
- [x] Vícejazyčnost (cs + en), kompletní překlady
- [x] README.md s instalačním návodem

### Plánováno 🔜

- [ ] **V5.0 – AI generátor testů**: využití `extracted_text` pro generování otázek pomocí Claude API
- [ ] Rate limiting na upload (zamezit spamu materiálů)
- [ ] Notifikační inbox (in-app notifikace místo jen emailů)
- [ ] Stažení více materiálů najednou (multi-select ZIP)
- [ ] Statistiky pro učitele (kolik materiálů má každý předmět/učitel)
- [ ] Verifikace materiálů učitelem před zveřejněním (workflow schválení)
