#!/bin/bash
set -e

echo "Waiting for PostgreSQL at ${DB_HOST:-db}:${DB_PORT:-5432}..."
until python -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        host=os.environ.get('DB_HOST','db'),
        port=os.environ.get('DB_PORT','5432'),
        dbname=os.environ.get('DB_NAME','edubase'),
        user=os.environ.get('DB_USER','edubase'),
        password=os.environ.get('DB_PASSWORD','edubase_secret'),
    )
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
  sleep 1
done

echo "PostgreSQL is ready."

# Ensure runtime directories exist
mkdir -p /app/logs /app/backups

# Only the web service runs migrations – celery worker sets SKIP_MIGRATE=1
if [ "${SKIP_MIGRATE:-0}" != "1" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
fi

exec "$@"
