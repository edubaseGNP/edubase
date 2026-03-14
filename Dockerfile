FROM python:3.13-slim

# System dependencies: PostgreSQL client, Tesseract OCR (cs + en), Node.js for Tailwind
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    postgresql-client \
    tesseract-ocr \
    tesseract-ocr-ces \
    tesseract-ocr-eng \
    poppler-utils \
    gettext \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV DJANGO_SETTINGS_MODULE=edubase.settings.dev \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install npm dependencies and build Tailwind CSS
# django-tailwind install/build delegates to npm scripts in theme/static_src/
RUN cd theme/static_src && npm install && npm run build

EXPOSE 8000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
