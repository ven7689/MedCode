# Medcode — AI Medical Document Coder

Automatically extract **ICD-10 diagnosis codes** from medical document images using a Vision-Language Model (VLM) via [OpenRouter](https://openrouter.ai).

Built with **Django REST Framework**, **Celery**, **Redis**, and **PostgreSQL** — fully containerised with Docker.

---

## Architecture

```
Client → POST /api/upload/ → Django (DRF) → Celery Task → OpenRouter VLM
                                                         ↓
Client ← GET /api/documents/<id>/ ← PostgreSQL ←── ICD-10 results stored
```

| Component | Technology |
|-----------|-----------|
| API Server | Django 4.2 + DRF |
| Task Queue | Celery 5 + Redis |
| Database | PostgreSQL 16 |
| VLM | NVIDIA Nemotron Nano 12B VL (via OpenRouter) |
| Container | Docker + Docker Compose |

---

## Quickstart

### Prerequisites
- Docker & Docker Compose
- An [OpenRouter](https://openrouter.ai) API key (free tier works)

### 1. Clone & configure

```bash
git clone https://github.com/your-username/medcode.git
cd medcode
cp .env.example .env
```

Edit `.env` and fill in your values:
```env
OPENROUTER_API_KEY=sk-or-v1-...
SECRET_KEY=your-django-secret-key
DB_PASSWORD=a-strong-password
```

### 2. Run with Docker

```bash
docker compose up --build
```

This starts:
- `db` — PostgreSQL
- `redis` — Redis broker
- `web` — Django API on port 8000
- `worker` — Celery worker

### 3. Run locally (without Docker)

```bash
# Requires PostgreSQL and Redis running locally
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# In a second terminal:
celery -A Medcode worker --loglevel=info
```

---

## API Reference

### `POST /api/upload/`

Upload a medical document image. Queues VLM processing asynchronously.

**Request** — `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `file` | Image | Medical document (JPEG, PNG, etc.) |

**Response** — `202 Accepted`
```json
{
  "id": 1,
  "file": "/media/documents/test.jpg",
  "status": "pending",
  "vlm_results": null,
  "error_message": null,
  "created_at": "2025-01-01T10:00:00Z"
}
```

---

### `GET /api/documents/<id>/`

Poll for results. Status transitions: `pending → processing → completed | failed`.

**Response** — `200 OK` (when completed)
```json
{
  "id": 1,
  "file": "/media/documents/test.jpg",
  "status": "completed",
  "vlm_results": [
    {"code": "J18.9", "description": "Pneumonia, unspecified organism"},
    {"code": "Z87.891", "description": "Personal history of nicotine dependence"}
  ],
  "error_message": null,
  "created_at": "2025-01-01T10:00:00Z"
}
```

---

## Running Tests

### Unit Tests
```bash
python manage.py test coder_app
```
Tests use mocks — no real API calls or external services needed.

### Live E2E Testing (Real Images + VLM)
To run a direct test of the VLM logic against real images in the `media/` folder (bypassing the HTTP server):
```bash
python live_test.py
```
This requires an active virtual environment and a valid `OPENROUTER_API_KEY` in your `.env`.

---

## Project Structure

```
Medcode/
├── Medcode/              # Django project settings, URLs, Celery config
│   ├── settings.py
│   ├── celery.py
│   └── urls.py
├── coder_app/            # Main application
│   ├── models.py         # MedicalDocument model
│   ├── views.py          # Upload + status endpoints
│   ├── serializers.py    # DRF serializers
│   ├── services.py       # VLM API call + image preprocessing
│   ├── tasks.py          # Celery task (process_document)
│   └── tests.py          # Full test suite
├── Dockerfile            # Multi-stage: web + worker
├── docker-compose.yml    # Orchestrates all services
├── requirements.txt
└── .env.example          # Environment variable template
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key | — |
| `SECRET_KEY` | Django secret key | insecure fallback |
| `DEBUG` | Debug mode | `True` |
| `DB_NAME` | PostgreSQL DB name | `medcode_db` |
| `DB_USER` | PostgreSQL user | `meduser` |
| `DB_PASSWORD` | PostgreSQL password | `medpass` |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |

---

## License

MIT
