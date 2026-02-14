# Credentials checklist

Use this to confirm your `.env` is set for the features you have.

| You have | Env variable(s) | Used for |
|----------|-----------------|----------|
| **OpenAI** | `OPENAI_API_KEY` | Keyword Generator (GPT) + GPT Analysis Engine |
| **Apify** | `APIFY_API_TOKEN` | TikTok, Instagram, Amazon scrapers |
| **YouTube** | `YOUTUBE_API_KEY` **or** `GOOGLE_API_KEY` | YouTube Data API (search, Shorts, comments). Only one needed. |
| **Google Sheets** | `GOOGLE_APPLICATION_CREDENTIALS` + `RESEARCH_SHEET_ID` | Write scraped data + analysis to your 5 tabs. `GOOGLE_APPLICATION_CREDENTIALS` = path to service account JSON (e.g. `./y-research-fd88f4abdece.json`). Share the Sheet with the service account email. |
| **Tavily** | `TAVILY_API_KEY` | Competitor analysis (competitors, ad library links) |
| **Gemini** | `GEMINI_API_KEY` **or** `GOOGLE_API_KEY` | Video analysis (hooks, CTAs, format) — Pipeline v2 |
| **Reddit** | — | No key; public API with User-Agent |

**Notes**

- **YouTube:** Use a **Google API key** (from [Google Cloud Console](https://console.cloud.google.com) → APIs → YouTube Data API v3). It usually starts with `AIza...`. Do not use your Apify token here.
- **Google Sheets:** You need both:
  1. `RESEARCH_SHEET_ID` — the ID from your Sheet URL.
  2. `GOOGLE_APPLICATION_CREDENTIALS` — full path to the service account JSON file (e.g. `./y-research-fd88f4abdece.json`). Share the Google Sheet with the service account email from that JSON.
