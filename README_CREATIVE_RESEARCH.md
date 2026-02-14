# Creative Agency Research Report — Stack

Generate a **Creative Agency Research Report** from a product link. The pipeline follows this architecture:

```
Product Link
    ↓
Keyword Generator (GPT)
    ↓
Scrapers (Reddit / YouTube / Amazon)
    ↓
Google Sheets (Database)  ← Reddit Comments | YouTube Videos | Amazon Reviews
    ↓
GPT Analysis Engine
    ↓
Insights + Avatars + Angles
    ↓
Final Report  (+ GPT Insights | Avatars written to Sheets)
```

- **Keyword Generator:** GPT produces search queries and subreddits from the product (and optional page content).
- **Scrapers:** Reddit (public API), YouTube Data API, Apify (Amazon/TikTok/Instagram), Tavily (competitor analysis).
- **Google Sheets:** First used as the **database** for scraped data (3 tabs); then analysis output is written to **GPT Insights** and **Avatars**.
- **Final report:** Full markdown report; optional Airtable and file output.

The report follows [CREATIVE_RESEARCH_REPORT_OUTLINE.md](./CREATIVE_RESEARCH_REPORT_OUTLINE.md) (videos analysis, comments analysis, avatar angles).

### Minimal credentials for testing

**Only one credential is required to run the full pipeline:**

- **`OPENAI_API_KEY`** — used for Keyword Generator (GPT) and GPT Analysis Engine.

With just this set, the pipeline will:
- Fetch the product page (no key).
- Generate keywords and subreddits (GPT).
- Run **Reddit** scraper only (no credentials; public API).
- **Skip** YouTube, Apify, and Tavily when their env vars are missing.
- **Skip** Google Sheets when `RESEARCH_SHEET_ID` or `GOOGLE_APPLICATION_CREDENTIALS` is missing.
- Produce the full report and optionally save it to a file (`-o report.md`).

```bash
cp .env.minimal .env   # add your OPENAI_API_KEY
python cron/generate_report_job.py "https://example.com/product" -o report.md
```

Add other keys when you need YouTube, Apify, Tavily, or Sheets.

---

## Stack overview

| Layer       | Services | Env / config |
|------------|----------|--------------|
| **Scraping** | Apify, YouTube, Reddit, **Tavily** (competitor analysis) | `APIFY_API_TOKEN`, `YOUTUBE_API_KEY` or `GOOGLE_API_KEY`, `TAVILY_API_KEY` (Reddit: no credentials) |
| **AI**       | OpenAI API | `OPENAI_API_KEY` (in `.env`) |
| **Storage**  | Google Sheets, Airtable | `RESEARCH_SHEET_ID` + `GOOGLE_APPLICATION_CREDENTIALS`; `AIRTABLE_API_KEY` + `AIRTABLE_BASE_ID` |
| **Automation** | Make.com or cron | Make webhook → run job; or `cron/generate_report_job.py` on a schedule |

---

## Setup

### 1. Clone and install

```bash
cd /path/to/freelancing
pip install -r requirements.txt
```

### 2. Environment variables

Copy `.env.example` to `.env` and fill in keys:

```bash
cp .env.example .env
```

**Required (minimal for testing):**

- `OPENAI_API_KEY` — from platform.openai.com. Only credential needed to test the pipeline; Reddit runs without a key, others are skipped if not set.

**Optional — scraping (report uses real data when set):**

- **Apify:** [apify.com](https://apify.com) → API token → `APIFY_API_TOKEN`
- **YouTube Data API v3:** [Google Cloud Console](https://console.cloud.google.com) → enable YouTube Data API v3 → create API key → `YOUTUBE_API_KEY` or `GOOGLE_API_KEY`
- **Reddit:** No credentials. The app uses Reddit’s public JSON API with `User-Agent: creative-research-bot/1.0`.
- **Tavily:** [tavily.com](https://tavily.com) → API key → `TAVILY_API_KEY`. Used for **competitor analysis** (competitors, Meta Ad Library, TikTok Creative Center, Google Ads Transparency). Free tier: 1,000 credits/month.

**Optional — storage:**

- **Airtable:** [airtable.com/account](https://airtable.com/account) → API key; base ID from base URL → `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`. Create a table e.g. “Research Reports” with columns: Product URL, Report Date, Report, Generated At.
- **Google Sheets:** Service account JSON from Google Cloud → set `GOOGLE_APPLICATION_CREDENTIALS` to file path. Create a Sheet and **5 tabs** named: **Reddit Comments** | **YouTube Videos** | **Amazon Reviews** | **GPT Insights** | **Avatars**. Share the sheet with the service account email. Set `RESEARCH_SHEET_ID` (from URL). The script will append rows to each tab (headers are added automatically if a tab is empty).

---

## Usage

### Quick: LLM-only report (no scraping)

Uses only `OPENAI_API_KEY`; fetches product page and generates report.

```bash
# Print to stdout
python run_research_report.py "https://www.amazon.com/dp/B0XXXXX"

# Save to file
python run_research_report.py "https://..." -o report.md --model gpt-4o-mini
```

### With scraping (Apify + YouTube + Reddit)

Set the optional scraping env vars, then:

```bash
python run_research_report.py "https://..." --scrape --queries "skincare" "anti-aging" --subreddits SkincareAddiction 30PlusSkinCare -o report.md
```

Scraped videos and comments are passed into the LLM for a data-grounded report.

### Full pipeline (architecture order)

Single entry point runs in order: **Keyword Generator (GPT) → Scrapers → Google Sheets (DB) → GPT Analysis → Insights + Avatars → Final Report.**

```bash
# From repo root; .env is loaded automatically
python cron/generate_report_job.py "https://example.com/product" -o report.md

# Override keywords (skip Keyword Generator for queries/subreddits)
python cron/generate_report_job.py "https://..." --queries "vitamin C serum" --subreddits SkincareAddiction -o report.md

# Do not write to Google Sheets
python cron/generate_report_job.py "https://..." -o report.md --no-sheets

# Disable cache (force fresh Apify, YouTube, Reddit, Tavily calls)
python cron/generate_report_job.py "https://..." -o report.md --no-cache

# Also save full report to Airtable
python cron/generate_report_job.py "https://..." -o report.md --airtable
```

- **Sheets:** Scraped data is written first (Reddit Comments, YouTube Videos, Amazon Reviews). After analysis, GPT Insights and Avatars tabs are updated.
- **Cache:** Successful Apify, YouTube, Reddit, and Tavily responses are stored under `.creative_research_cache/` so repeated runs reuse them (saves quota when testing). Disable with `--no-cache` or `CREATIVE_RESEARCH_NO_CACHE=1`. Optional: set `CREATIVE_RESEARCH_CACHE_DIR` to use another directory.
- Use this script from **cron** or **Make.com** (see Automation).

---

## Automation

### Option A: Python cron

Example crontab (run daily at 9 AM; adjust path and product URL):

```cron
0 9 * * * cd /path/to/freelancing && . .env 2>/dev/null; python cron/generate_report_job.py "https://your-product-url" --queries "your" "keywords" -o reports/daily.md >> cron.log 2>&1
```

Or use a wrapper script that sources `.env` and calls `generate_report_job.py`.

### Option B: Make.com (free tier)

1. Create a scenario: **Webhook** → **Run script** (or **HTTP** to a server that runs the job).
2. Webhook payload can include `product_link`, optional `queries`, `subreddits`.
3. In “Run script”, use **Python** (or call your server): load env from Make’s variables, then run `cron/generate_report_job.py` with the webhook payload (e.g. `product_link` and `-o` to a known path, or rely on Airtable/Sheets only).
4. Optionally add a **Google Sheets** or **Airtable** step to append the report if you did not use the built-in storage in the job.

---

## MCP server (optional)

For Cursor/Claude integration:

```bash
python -m creative_research.mcp_server
```

Add the server in Cursor (stdio) with command `python`, args `["-m", "creative_research.mcp_server"]`, **cwd** = repo root, **env** = `OPENAI_API_KEY`. Then use the tool **generate_creative_research_report(product_link, output_path?, model?)**.

---

## Files

| File | Purpose |
|------|--------|
| `.env` | API keys (copy from `.env.example`) |
| `CREATIVE_RESEARCH_REPORT_OUTLINE.md` | Report structure and checklist |
| `creative_research/pipeline.py` | **Pipeline:** Product Link → Keywords (GPT) → Scrapers → Sheets (DB) → GPT Analysis → Final Report |
| `creative_research/keyword_generator.py` | Keyword Generator (GPT): product → search_queries + subreddits |
| `creative_research/report_generator.py` | GPT Analysis Engine: product + scraped data → full report (Insights + Avatars + Angles) |
| `creative_research/cache.py` | File cache for Apify, YouTube, Reddit, Tavily (`.creative_research_cache/`) |
| `creative_research/scraped_data.py` | ScrapedData and video/comment structs |
| `creative_research/scrapers/*.py` | Scrapers: Reddit, YouTube, Apify (Amazon/TikTok/Instagram), Tavily (competitors) |
| `creative_research/storage/sheets_storage.py` | Google Sheets: save_scraped_data_to_sheets (DB), save_analysis_to_sheets (Insights + Avatars) |
| `creative_research/storage/airtable_storage.py` | Save report row to Airtable |
| `cron/generate_report_job.py` | Run full pipeline (architecture order); optional -o, --no-sheets, --airtable |
| `run_research_report.py` | CLI: LLM-only or --scrape with optional save (no pipeline) |

---

## Notes

- **OPENAI_API_KEY** is read from `.env` by the CLI and cron job (via `python-dotenv`).
- **Quotas:** YouTube Data API has a daily quota; Reddit and Apify have free-tier limits. The script skips a source if its env vars are missing.
- **Pipeline:** The default flow is Product Link → Keyword Generator (GPT) → Scrapers → Google Sheets (DB) → GPT Analysis → Insights + Avatars → Final Report. Sheets is used first as the database for scraped data, then analysis is written to GPT Insights and Avatars tabs.
