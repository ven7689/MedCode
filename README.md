# Medcode — AI-Powered Medical Document Coder

> Automatically extract **ICD-10 diagnosis codes** from scanned medical document images using a Vision-Language Model pipeline — no manual lookup, no guesswork.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-092E20?logo=django&logoColor=white)](https://djangoproject.com)
[![Celery](https://img.shields.io/badge/Celery-5.x-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

Medical billing teams invest significant time manually reviewing patient records and mapping diagnoses to ICD-10 codes. **Medcode** automates this workflow end-to-end:

1. A scanned medical document (JPEG/PNG) is **uploaded** via a REST API
2. The image is **queued asynchronously** through Celery + Redis
3. A **Vision-Language Model** (NVIDIA Nemotron Nano 12B VL via OpenRouter) reads the document and extracts all relevant ICD-10 codes with clinical descriptions
4. Results are **persisted in PostgreSQL** and retrievable at any time via a simple polling endpoint

```
Client ──► POST /api/upload/ ──► Django DRF ──► Celery Task ──► OpenRouter VLM
                                                                       │
Client ◄── GET /api/documents/<id>/ ◄── PostgreSQL ◄──── ICD-10 results stored
```

---

## Technology Stack

| Layer         | Technology                                        |
|---------------|---------------------------------------------------|
| **API Server**    | Django 4.2 + Django REST Framework            |
| **Task Queue**    | Celery 5 + Redis 7                            |
| **Database**      | PostgreSQL 16                                 |
| **VLM**           | NVIDIA Nemotron Nano 12B VL (via OpenRouter)  |
| **Image Processing** | Pillow 10                                  |
| **Container**     | Docker + Docker Compose (multi-stage builds)  |
| **Runtime**       | Python 3.11 / Gunicorn (2 workers)            |

---

## Architecture

The application is composed of four containerised services, all orchestrated by Docker Compose with health-check–based startup ordering:

```
┌─────────────────────────────────────────────────┐
│                Docker Compose                    │
│                                                 │
│  ┌──────────┐   ┌──────────┐                   │
│  │  db      │   │  redis   │                   │
│  │ Postgres │   │  Broker  │                   │
│  └────┬─────┘   └────┬─────┘                   │
│       │ healthy      │ healthy                  │
│       └──────┬───────┘                          │
│              │                                  │
│   ┌──────────┴──────────┐                       │
│   │         web         │                       │
│   │  Django + Gunicorn  │ :8000                 │
│   └─────────────────────┘                       │
│   ┌─────────────────────┐                       │
│   │       worker        │                       │
│   │   Celery Consumer   │                       │
│   └─────────────────────┘                       │
└─────────────────────────────────────────────────┘
```

**Document status lifecycle:** `pending → processing → completed | failed`

---

## Quickstart

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- An [OpenRouter](https://openrouter.ai) API key (free tier is sufficient)

### 1. Clone and configure

```bash
git clone https://github.com/your-username/medcode.git
cd medcode
cp .env.example .env
```

Open `.env` and fill in your credentials:

```env
OPENROUTER_API_KEY=sk-or-v1-...
SECRET_KEY=your-django-secret-key
DB_PASSWORD=a-strong-password
```

### 2. Build and start all services

```bash
docker compose up --build
```

This builds and starts four containers. The `web` container automatically runs database migrations on first boot.

| Service   | Role                           | Port   |
|-----------|--------------------------------|--------|
| `db`      | PostgreSQL 16 database         | —      |
| `redis`   | Celery message broker          | —      |
| `web`     | Django REST API (Gunicorn)     | `8000` |
| `worker`  | Celery async task processor    | —      |

### 3. Upload a document

```bash
curl -X POST http://localhost:8000/api/upload/ \
  -F "file=@your_medical_doc.jpg"
```

### 4. Retrieve results

```bash
curl http://localhost:8000/api/documents/1/
```

---

## API Reference

### `POST /api/upload/`

Upload a medical document image. Processing is dispatched asynchronously; the endpoint returns immediately with a `202 Accepted`.

**Request** — `multipart/form-data`

| Field  | Type  | Required | Description                          |
|--------|-------|----------|--------------------------------------|
| `file` | image | ✅       | Scanned medical document (JPEG, PNG) |

**Response** — `202 Accepted`

```json
{
  "id": 1,
  "file": "/media/documents/sample.jpg",
  "status": "pending",
  "vlm_results": null,
  "error_message": null,
  "created_at": "2025-01-01T10:00:00Z"
}
```

---

### `GET /api/documents/<id>/`

Poll for processing results. Repeat until `status` is `"completed"` or `"failed"`.

**Response** — `200 OK`

```json
{
  "id": 1,
  "file": "/media/documents/sample.jpg",
  "status": "completed",
  "vlm_results": [
    { "code": "J18.9",   "description": "Pneumonia, unspecified organism" },
    { "code": "Z87.891", "description": "Personal history of nicotine dependence" }
  ],
  "error_message": null,
  "created_at": "2025-01-01T10:00:00Z"
}
```

---

## Project Structure

```
Medcode/
├── Medcode/                  # Django project: settings, URLs, Celery config
│   ├── settings.py
│   ├── celery.py
│   └── urls.py
├── coder_app/                # Core application
│   ├── models.py             # MedicalDocument model + status state machine
│   ├── views.py              # Upload & status API endpoints
│   ├── serializers.py        # DRF serializers
│   ├── services.py           # VLM API call + image preprocessing (Pillow)
│   ├── tasks.py              # Celery task: process_document
│   └── tests.py              # Unit test suite (fully mocked)
├── Dockerfile                # Multi-stage build: base → web | worker
├── docker-compose.yml        # Service orchestration (4 services, health-checks)
├── live_test.py              # End-to-end integration test with real images
├── requirements.txt
└── .env.example
```

---

## Running Tests

### Unit Tests (mocked — no external API calls required)

```bash
python manage.py test coder_app
```

Covers document upload, async task dispatching, processing state transitions, and failure handling.

### Live End-to-End Test (real images + VLM)

```bash
python live_test.py
```

Requires a valid `OPENROUTER_API_KEY` set in `.env`. Uploads real images from the `media/documents/` directory and validates the full pipeline.

---

## Environment Variables

| Variable             | Description                        | Default                      |
|----------------------|------------------------------------|------------------------------|
| `OPENROUTER_API_KEY` | OpenRouter API key                 | —                            |
| `SECRET_KEY`         | Django secret key                  | insecure fallback (dev only) |
| `DEBUG`              | Django debug mode                  | `True`                       |
| `DB_NAME`            | PostgreSQL database name           | `medcode_db`                 |
| `DB_USER`            | PostgreSQL user                    | `meduser`                    |
| `DB_PASSWORD`        | PostgreSQL password                | `medpass`                    |
| `DB_HOST`            | PostgreSQL host                    | `localhost` / `db` (Docker)  |
| `DB_PORT`            | PostgreSQL port                    | `5432`                       |
| `REDIS_URL`          | Redis connection URL               | `redis://localhost:6379/0`   |

> **Note:** Never commit `.env` to version control. Use `.env.example` as a template and keep secrets out of source code.

---

## Planned Improvements

| Feature | Description |
|---------|-------------|
| **WebSocket result push** | Eliminate polling — push results to the client via WebSocket when processing completes |
| **Retry with backoff** | Celery exponential backoff on VLM network errors or malformed responses |
| **Structured output enforcement** | Use OpenRouter JSON mode or grammar-constrained sampling to guarantee parseable ICD-10 JSON |
| **Frontend UI** | React or HTMX interface for document upload and live result display |
| **Auth & multi-tenancy** | JWT-based authentication for isolated, multi-team deployments |
| **Confidence scores** | Ask the VLM to return a confidence level per code for human-in-the-loop review |

---

## License

This project is licensed under the [MIT License](LICENSE).
