# Credentials checklist

Use this to confirm your `.env` is set for the features you need. Copy from `.env.example` and fill in values.

## Pipeline / Creative Research

| You have | Env variable(s) | Used for |
|----------|-----------------|----------|
| **OpenAI** | `OPENAI_API_KEY` | Keywords, report, scripts (primary; Gemini used as fallback if OpenAI fails) |
| **Apify** | `APIFY_API_TOKEN` | TikTok, Instagram, Amazon scrapers |
| **YouTube** | `YOUTUBE_API_KEY` **or** `GOOGLE_API_KEY` | YouTube Data API (search, Shorts, comments) |
| **Tavily** | `TAVILY_API_KEY` | Competitor research |
| **Gemini** | `GEMINI_API_KEY` **or** `GOOGLE_API_KEY` | Video analysis (hooks, CTAs, format); fallback for keywords/report/scripts when OpenAI fails |
| **Reddit** | — | No key; public API with User-Agent |

## Django API

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | Django secret (change in production) |
| `DJANGO_DEBUG` | 1 for dev, 0 for production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts |
| `USE_SQLITE` | 1 to use SQLite instead of PostgreSQL |
| `POSTGRES_*` | Database connection |
| `CELERY_BROKER_URL` | Redis for async pipeline |
| `NGROK_SHARING` | true when sharing via ngrok |
| `CORS_ALLOWED_ORIGINS` | Allowed frontend origins |

## Notes

- **YouTube:** Use a **Google API key** (from [Google Cloud Console](https://console.cloud.google.com) → APIs → YouTube Data API v3). It usually starts with `AIza...`.
- See `.env.example` for full list and defaults.
