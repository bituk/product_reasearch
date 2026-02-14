#!/usr/bin/env python3
"""
Full pipeline (architecture):

  Product Link
       ↓
  Keyword Generator (GPT)
       ↓
  Scrapers (Reddit / YouTube / Amazon)
       ↓
  Google Sheets (Database) — Reddit Comments | YouTube Videos | Amazon Reviews
       ↓
  GPT Analysis Engine
       ↓
  Insights + Avatars + Angles
       ↓
  Final Report (+ save to GPT Insights | Avatars)

Usage:
  python cron/generate_report_job.py "https://example.com/product"
  python cron/generate_report_job.py   # uses PRODUCT_URL from .env
  python cron/generate_report_job.py -o report.md --no-sheets
  python cron/generate_report_job.py --queries "skincare" "serum" --subreddits SkincareAddiction  # override keywords

Env: OPENAI_API_KEY required. Optional: PRODUCT_URL (used when no URL given on command line),
     APIFY_API_TOKEN, YOUTUBE_API_KEY, TAVILY_API_KEY, GOOGLE_APPLICATION_CREDENTIALS,
     RESEARCH_SHEET_ID, AIRTABLE_*.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline: Product Link → Keywords (GPT) → Scrapers → Sheets (DB) → GPT Analysis → Final Report")
    parser.add_argument("product_link", nargs="?", default=None, help="Product URL (default: PRODUCT_URL from .env)")
    parser.add_argument("-o", "--output", help="Save final report to this file (Markdown)")
    parser.add_argument("--queries", nargs="+", default=None, help="Override: search queries (skip Keyword Generator)")
    parser.add_argument("--subreddits", nargs="+", default=None, help="Override: subreddits (skip Keyword Generator)")
    parser.add_argument("--no-sheets", action="store_true", help="Do not write to Google Sheets")
    parser.add_argument("--no-cache", action="store_true", help="Disable scraper/API cache (force fresh Apify, YouTube, Reddit, Tavily)")
    parser.add_argument("--airtable", action="store_true", help="Also save full report to Airtable")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model")
    args = parser.parse_args()
    if args.no_cache:
        os.environ["CREATIVE_RESEARCH_NO_CACHE"] = "1"

    product_link = (args.product_link or os.environ.get("PRODUCT_URL") or "").strip()
    if not product_link:
        print("Error: provide a product URL as argument or set PRODUCT_URL in .env", file=sys.stderr)
        return 1

    from creative_research.pipeline import run_pipeline
    from creative_research.storage.airtable_storage import save_report_to_airtable
    from creative_research.cache import is_cache_enabled, get_and_clear_cache_hits
    save_to_sheets = not args.no_sheets

    if is_cache_enabled():
        print("Cache: enabled (scrapers will use cached data when available; use --no-cache to force fresh).", flush=True)
    else:
        print("Cache: disabled (--no-cache).", flush=True)

    # Run pipeline (Keyword Generator → Scrapers → Sheets DB → GPT Analysis → Insights + Avatars → save analysis to Sheets)
    print("1) Keyword Generator (GPT)...", flush=True)
    result = run_pipeline(
        product_link,
        model=args.model,
        save_to_sheets=save_to_sheets,
        search_queries_override=args.queries,
        subreddits_override=args.subreddits,
    )
    if result.get("keywords", {}).get("search_queries"):
        print(f"   Keywords: {result['keywords']['search_queries'][:5]}...", flush=True)
    print("2) Scrapers done.", flush=True)
    if result.get("sheets_scraped"):
        print(f"3) DB: {result['sheets_scraped']}", flush=True)
    print("4) GPT Analysis done.", flush=True)
    if result.get("sheets_analysis"):
        print(f"5) Analysis saved: {result['sheets_analysis']}", flush=True)

    hits = get_and_clear_cache_hits()
    if hits:
        print(f"Cache used for: {', '.join(sorted(set(hits)))}", flush=True)
    elif is_cache_enabled():
        print("Cache: no hits this run (all data fetched from APIs).", flush=True)

    report = result.get("report") or ""

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"Final report saved to {out}", flush=True)

    if args.airtable:
        msg = save_report_to_airtable(product_link, report)
        print(msg, flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
