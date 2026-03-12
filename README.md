# EduBase

Open-source school materials platform. Share and browse learning materials organized by school year and subject, with full-text search, OCR extraction, and a clean admin dashboard.

## Features

- **Google OAuth** login (optionally restricted to one school domain)
- **Role-based access**: Student, Teacher, VIP Student, Admin
- **Material upload** (PDF, images) with automatic OCR text extraction (Celery + Tesseract)
- **Full-text search** with subject/year filters and search analytics
- **Admin dashboard** with charts, audit log, and export (CSV/Excel/ZIP)
- **Multilingual**: Czech (default) and English

## Requirements

- [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/install/)
- A Google Cloud project with OAuth 2.0 credentials (for login)

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/<your-org>/edubase.git
cd edubase

# 2. Create environment file
cp .env.example .env
# Edit .env – fill in SECRET_KEY, DB_PASSWORD, and optionally GOOGLE_ALLOWED_DOMAIN

# 3. Build and start
docker compose up --build -d

# 4. Open the setup wizard
open http://localhost:8000
```

The setup wizard will guide you through:
1. School name and domain
2. Google OAuth credentials
3. First admin account

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (generate a new one!) | *change-me* |
| `DEBUG` | Debug mode (`True`/`False`) | `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database name | `edubase` |
| `DB_USER` | PostgreSQL user | `edubase` |
| `DB_PASSWORD` | PostgreSQL password | *required* |
| `GOOGLE_ALLOWED_DOMAIN` | Restrict Google login to domain (e.g. `skola.cz`) | *(all domains)* |
| `MATERIAL_MAX_UPLOAD_MB` | Max upload file size in MB | `50` |
| `REDIS_URL` | Redis URL for Celery | `redis://redis:6379/0` |

## Generating a Secret Key

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Docker Services

| Service | Description |
|---------|-------------|
| `web` | Django application (Gunicorn, port 8000) |
| `db` | PostgreSQL 16 |
| `redis` | Redis 7 (Celery broker) |
| `celery` | Celery worker (OCR background tasks) |

## Development

```bash
# Start in development mode (with live reload)
docker compose up

# Run tests
docker compose exec web python manage.py test

# Create a superuser manually
docker compose exec web python manage.py createsuperuser

# Apply migrations
docker compose exec web python manage.py migrate

# Collect static files
docker compose exec web python manage.py collectstatic --noinput

# Compile translations
docker compose exec web python manage.py compilemessages --locale cs --locale en
```

## Updating

```bash
git pull
docker compose build web celery
docker compose exec web python manage.py migrate
docker compose exec web python manage.py compilemessages --locale cs --locale en
docker compose restart web celery
```

## Production Deployment (Proxmox / VPS)

1. Point your domain DNS to the server IP
2. Set `ALLOWED_HOSTS=yourdomain.cz` in `.env`
3. Set `DEBUG=False` and a strong `SECRET_KEY`
4. Put Nginx/Caddy in front of port 8000 for HTTPS
5. Run `docker compose up -d`

### Nginx example

```nginx
server {
    listen 443 ssl;
    server_name edubase.yourdomain.cz;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 55M;
    }
}
```

## License

MIT
