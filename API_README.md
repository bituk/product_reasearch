# Product Research API

Django REST Framework API for running the product research pipeline and tracking job status.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. PostgreSQL

Ensure PostgreSQL is running. Create the database:

```bash
createdb product_research
```

Or with psql:

```sql
CREATE DATABASE product_research;
```

### 3. Environment

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

**Minimal for API** (PostgreSQL defaults):

```
POSTGRES_DB=product_research
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

**Pipeline** requires `OPENAI_API_KEY` and `PRODUCT_URL`. See `.env.example` for full options (Apify, YouTube, Gemini, Celery, CORS, etc.).

### 4. Migrations

```bash
cd api
python manage.py migrate
```

### 5. Run server

```bash
cd api
python manage.py runserver
```

**SQLite for testing** (when PostgreSQL not available):
```bash
USE_SQLITE=1 cd api && python manage.py migrate && python manage.py runserver
```

### 6. Celery (optional, for async pipeline)

Requires Redis. When Redis is unavailable, the API falls back to threading.

```bash
# Install Redis, then:
celery -A api worker -l info
```

Env: `CELERY_BROKER_URL=redis://localhost:6379/0` (default). See `.env.example`.

## API Endpoints

### 1. Start Pipeline

**POST** `/api/pipeline/start/`

Start the product research pipeline for a product URL. Returns immediately with job ID; pipeline runs in background.

**Request body:**
- `product_url` (optional): defaults to `PRODUCT_URL` from `.env` when omitted
- `skip_apify` (optional): when `true`, skip Apify scrapers

**Request:**
```json
{
  "product_url": "https://www.flipkart.com/product-url"
}
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "product_url": "https://www.flipkart.com/product-url",
  "status": "pending",
  "current_stage": null,
  "error_message": null,
  "created_at": "2026-02-16T10:00:00Z",
  "updated_at": "2026-02-16T10:00:00Z",
  "completed_at": null,
  "stages": []
}
```

### 2. Get Job Status

**GET** `/api/pipeline/status/<job_id>/`

Get the current status and stage of a pipeline job. When completed, includes full report, scripts, and structured data.

**Response (running):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "product_url": "https://...",
  "status": "running",
  "current_stage": "video_scrape",
  "error_message": null,
  "created_at": "2026-02-16T10:00:00Z",
  "updated_at": "2026-02-16T10:05:00Z",
  "completed_at": null,
  "stages": [
    {"stage_name": "fetch_product", "status": "completed", ...},
    {"stage_name": "keywords", "status": "completed", ...},
    {"stage_name": "video_scrape", "status": "running", ...},
    ...
  ]
}
```

**Response (completed):** Same as above plus `report`, `scripts`, `keywords`, `video_analyses`, `download_results`, `scraped_data_summary`.

## Database Schema

- **pipeline_job**: Main job record (product_url, status, report, scripts, JSON fields for structured data)
- **pipeline_stage**: Per-stage tracking (fetch_product, keywords, video_scrape, download, analysis, report, scripts)
