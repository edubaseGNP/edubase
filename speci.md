# Specifikace projektu: EduBase (Open-Source Školní Databáze Materiálů)

## 1. Cíl projektu a Role
Jsi expertní full-stack softwarový inženýr. Tvým úkolem je autonomně vyvíjet "EduBase" – open-source platformu pro sdílení učebních materiálů ve školním prostředí. 
Cílem je aplikace snadno nasaditelná na lokální školní servery (Proxmox/Docker), která je připravená na budoucí napojení AI pro generování testů z nahraných materiálů (V5.0).
Projekt musí od začátku podporovat **multijazyčnost** (i18n).

## 2. Technologický stack
* **Backend a Framework:** Python + Django (ideální pro bezpečnost a budoucí AI integrace).
* **Frontend:** Django Templates + Tailwind CSS (čistý, moderní design, responzivní). Volitelně HTMX pro dynamické prvky.
* **Databáze:** PostgreSQL.
* **Autentizace:** Django Allauth (exkluzivně Google OAuth pro školní doménu).
* **Zpracování souborů a OCR:** Nahrávání PDF a obrázků. Obrázky musí být automaticky komprimovány/optimalizovány. Pro přípravu na V5.0 implementuj **extrakci textu** (např. pomocí `pytesseract` pro obrázky a naskenovaná PDF, a `pdfminer` pro textová PDF).
* **Verzování a CI/CD:** GitHub (včetně nastavení GitHub Actions).
* **Infrastruktura:** Docker a `docker-compose.yml` připravené pro Proxmox (lokální hosting, včetně instalace Tesseract OCR v Dockerfile).

## 3. Uživatelé a Oprávnění (RBAC)
Všichni nově přihlášení přes Google mají v základu roli **Student**.
1. **Student:** Může číst materiály svých předmětů. Na homepage si může navolit 3-4 oblíbené/časté předměty pro rychlý přístup.
2. **Učitel:** Práva přiděluje Admin. Může spravovat konkrétní ročníky, vytvářet hlavní stack materiálů a přidělovat VIP práva studentům.
3. **VIP Student:** Student, kterému Učitel nebo Admin udělil speciální práva pro konkrétní předmět (např. možnost nahrávat/editovat materiály).
4. **Admin:** Má plný přístup, přiděluje role (Učitel/Admin) a tvoří strukturu školy.

## 4. Hlavní funkce databáze
* **Struktura:** Ročník (např. Sexta D) -> Předmět (např. Český jazyk) -> Typ materiálu (Podklady, Testy, Kontrolní otázky).
* **Metadata souborů a Text pro AI:** U každého nahraného materiálu se loguje datum, historie úprav a autor. Zároveň databázový model obsahuje skryté pole `extracted_text` (TextFiled), kam se při uploadu na pozadí uloží čistý text vytěžený přes OCR pro budoucí využití umělou inteligencí.
* **Soukromí:** Autor má možnost nastavit, jak se zobrazí jeho identita (Celé jméno / Iniciály / Anonymně + ročník nástupu).
* **Robustní logování:** Veškeré úpravy a mazání musí být logovány pro audit.

## 5. Pravidla pro AI vývojáře (Vibe Coding Guidelines)
* **Jazyk a formát:** Kód, názvy proměnných a komentáře piš ideálně anglicky (nebo česky, pokud to dává větší smysl pro doménovou logiku školy). Komunikuj se mnou česky.
* **Workflow a Autonomie:** Máš volnost. Pracuj autonomně, rovnou implementuj a ověřuj funkcionalitu. Neptej se mě na každý řádek kódu. Zastav se a zeptej se mě POUZE u důležitých rozcestníků (např. návrh databázového schématu, struktura UI, výběr knihovny).
* **Čistota kódu:** Udržuj modularitu. Rozděluj Django do logických aplikací (např. `users`, `materials`, `core`).
* **Krokování:** Při zahájení si přečti tuto specifikaci a začni Krokem 1. Po jeho otestování a mém schválení přejdi na další.

## 6. Milníky pro implementaci (Roadmap)
* **Krok 1:** Inicializace Django projektu, nastavení Dockeru (včetně Tesseract OCR vrstvy), PostgreSQL a integrace Tailwind CSS.
* **Krok 2:** Implementace vlastního uživatelského modelu, Google OAuth přihlašování a systém rolí (Student, Učitel, Admin, VIP). Připravit multijazyčnost.
* **Krok 3:** Databázové modely pro Ročníky, Předměty a Materiály. Systém správy a přidělování VIP práv. Databázový model pro materiál musí obsahovat pole pro vytěžený text.
* **Krok 4:** Logika pro nahrávání souborů. Automatická komprese obrázků a **background task (např. přes Celery nebo jednoduchý thread) pro OCR extrakci textu**, který uloží výsledek do databáze. Logování akcí.
* **Krok 5:** Frontend - Zobrazení materiálů, customizace studentské homepage (výběr oblíbených předmětů), UI pro vyhledávání nad extrahovaným textem.
