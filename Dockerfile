FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ---------------------------------------------------------------------------
# Web stage  (gunicorn)
# ---------------------------------------------------------------------------
FROM base AS web
EXPOSE 8000
CMD ["gunicorn", "Medcode.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]

# ---------------------------------------------------------------------------
# Worker stage  (Celery)
# ---------------------------------------------------------------------------
FROM base AS worker
CMD ["celery", "-A", "Medcode", "worker", "--loglevel=info", "--concurrency=2"]
