#  Medcode — AI-Powered Medical Document Coder

> Automatically extract **ICD-10 diagnosis codes** from scanned medical document images — no manual entry, no guesswork.

Built end-to-end in under a week using **vibe coding** (AI-assisted development). The entire stack — Django REST API, async Celery pipeline, PostgreSQL, Redis, and Docker Compose orchestration — was designed and iterated with AI as a collaborative pair programmer.

---

##  What It Does

Medical billing teams spend enormous time manually reviewing patient documents and matching diagnoses to ICD-10 codes. Medcode automates this:

1. **Upload** a scanned medical document (JPEG/PNG) via REST API
2. The image is **queued asynchronously** via Celery + Redis
3. A **Vision-Language Model** (NVIDIA Nemotron Nano 12B VL via OpenRouter) reads the document and extracts all relevant ICD-10 codes with descriptions
4. Results are **stored in PostgreSQL** and retrievable at any time

```
Client → POST /api/upload/ → Django (DRF) → Celery Task → OpenRouter VLM
                                                         ↓
Client ← GET /api/documents/<id>/ ← PostgreSQL ←── ICD-10 results stored
```

| Component   | Technology                                   |
|-------------|----------------------------------------------|
| API Server  | Django 4.2 + Django REST Framework           |
| Task Queue  | Celery 5 + Redis 7                           |
| Database    | PostgreSQL 16                                |
| VLM         | NVIDIA Nemotron Nano 12B VL (via OpenRouter) |
| Container   | Docker + Docker Compose (multi-stage builds) |

---

##  AI Tools Used

This project was built using **Antigravity (Google DeepMind)** as the primary AI pair programmer throughout the entire development lifecycle — not just for boilerplate, but for architecture decisions, debugging, iterative design, and even writing this README.

Specific things the AI helped with:

- **Architecture design** — debating async vs. sync processing, choosing Celery over Django Channels for this use case
- **VLM prompt engineering** — crafting the system prompt to reliably extract structured ICD-10 JSON from noisy medical scans
- **Django + Celery wiring** — task definitions, signal handling, and status state machine (`pending → processing → completed | failed`)
- **Docker multi-stage builds** — keeping the `web` and `worker` images lean, sharing a single `base` layer
- **Healthcheck orchestration** — ensuring `web` and `worker` only start after `db` and `redis` pass their healthchecks
- **Test suite** — generating mocked unit tests that cover upload, processing, and failure paths without real API calls
- **Debugging** — tracked down a `psycopg2` driver conflict, Redis URL mismatch between local and Docker environments, and a Celery task serialization issue

---

##  What I Learned

- **Vibe coding multiplies output, but you still drive.** The AI is fastest when you give it clear intent and constraints. Vague prompts produce vague code. Specific architectural intent produces production-quality output.
- **Async pipelines require more design upfront.** Getting Celery, Redis, and Django to coordinate cleanly — especially in Docker with dependency healthchecks — requires understanding what you're building, not just copy-pasting.
- **VLM output is non-deterministic.** The model sometimes returns freeform text instead of clean JSON. Defensive parsing and retry logic are non-negotiable in production.
- **Docker Compose is a great learning tool.** Writing the compose file myself (with AI feedback) gave me a much deeper understanding of networking, volumes, and service dependencies than any tutorial.
- **AI pair programming changes the feedback loop.** Instead of waiting hours to debug a config issue, you can describe the symptom and get a targeted hypothesis in seconds.

---

##  What I'd Improve

- **Webhook / WebSocket results push** — instead of polling `GET /api/documents/<id>/`, push results to the client when processing completes
- **Retry + backoff on VLM failures** — Celery task should retry with exponential backoff on network errors or malformed VLM responses
- **Structured output enforcement** — use OpenRouter's JSON mode or a grammar-constrained sampler to guarantee parseable ICD-10 JSON every time
- **Frontend UI** — a simple React or HTMX interface for uploading documents and watching results come in live
- **Auth + multi-tenancy** — JWT-based auth so multiple billing teams can use the same deployment with isolated data
- **Confidence scores** — ask the VLM to return a confidence level per code, so reviewers know which extractions need a human second look

---

##  Quickstart

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

### 2. Build & run

```bash
docker compose up --build
```

This starts 4 containers:

| Service  | Role                              |
|----------|-----------------------------------|
| `db`     | PostgreSQL 16 database            |
| `redis`  | Celery message broker             |
| `web`    | Django API on `localhost:8000`    |
| `worker` | Celery async task processor       |

> The `web` container automatically runs `python manage.py migrate` on first boot.

### 3. Upload a document

```bash
curl -X POST http://localhost:8000/api/upload/ \
  -F "file=@your_medical_doc.jpg"
```

### 4. Poll for results

```bash
curl http://localhost:8000/api/documents/1/
```

---

##  API Reference

### `POST /api/upload/`

Upload a medical document image. Queues VLM processing asynchronously.

**Request** — `multipart/form-data`

| Field  | Type  | Description                        |
|--------|-------|------------------------------------|
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

Poll for results. Status transitions: `pending → processing → completed | failed`

**Response** — `200 OK` (when completed)
```json
{
  "id": 1,
  "file": "/media/documents/test.jpg",
  "status": "completed",
  "vlm_results": [
    {"code": "J18.9",    "description": "Pneumonia, unspecified organism"},
    {"code": "Z87.891",  "description": "Personal history of nicotine dependence"}
  ],
  "error_message": null,
  "created_at": "2025-01-01T10:00:00Z"
}
```

---

##  Tests

### Unit Tests (mocked — no API calls needed)
```bash
python manage.py test coder_app
```

### Live E2E Test (real images + VLM)
```bash
python live_test.py
```
Requires a valid `OPENROUTER_API_KEY` in `.env`.

---

##  Project Structure

```
Medcode/
├── Medcode/              # Django project settings, URLs, Celery config
│   ├── settings.py
│   ├── celery.py
│   └── urls.py
├── coder_app/            # Main application
│   ├── models.py         # MedicalDocument model + status choices
│   ├── views.py          # Upload + status endpoints
│   ├── serializers.py    # DRF serializers
│   ├── services.py       # VLM API call + image preprocessing
│   ├── tasks.py          # Celery task (process_document)
│   └── tests.py          # Full unit test suite
├── Dockerfile            # Multi-stage build: base → web / worker
├── docker-compose.yml    # Orchestrates all 4 services
├── requirements.txt
└── .env.example
```

---

##  Environment Variables

| Variable             | Description              | Default                    |
|----------------------|--------------------------|----------------------------|
| `OPENROUTER_API_KEY` | OpenRouter API key       | —                          |
| `SECRET_KEY`         | Django secret key        | insecure fallback          |
| `DEBUG`              | Debug mode               | `True`                     |
| `DB_NAME`            | PostgreSQL database name | `medcode_db`               |
| `DB_USER`            | PostgreSQL user          | `meduser`                  |
| `DB_PASSWORD`        | PostgreSQL password      | `medpass`                  |
| `DB_HOST`            | PostgreSQL host          | `localhost` / `db` in Docker |
| `DB_PORT`            | PostgreSQL port          | `5432`                     |
| `REDIS_URL`          | Redis connection URL     | `redis://localhost:6379/0` |

---

## License

MIT
