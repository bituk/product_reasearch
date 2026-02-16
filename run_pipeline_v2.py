#!/usr/bin/env python3
"""
Run Pipeline v2: Research doc → Video scrape → Download → Analysis → Competitor research → LLM generation → Scripts.

Uses PRODUCT_URL from .env. All API responses (Apify, YouTube, Tavily, Gemini, etc.) are cached.
"""

import argparse
import os
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from creative_research.pipeline_v2 import run_pipeline_v2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Pipeline v2 (uses PRODUCT_URL from .env)")
    parser.add_argument("-o", "--output", help="Save report + scripts to file")
    parser.add_argument("--product-url", help="Override PRODUCT_URL from .env")
    parser.add_argument("--no-download", action="store_true", help="Skip video download (faster, uses URLs only)")
    parser.add_argument("--skip-apify", action="store_true", help="Skip Apify scrapers (if Apify client crashes)")
    args = parser.parse_args()
    if args.skip_apify:
        os.environ["SKIP_APIFY"] = "1"

    from creative_research.constants import PRODUCT_URL
    product_url = (args.product_url or PRODUCT_URL or "").strip()
    if not product_url:
        print("Error: PRODUCT_URL not set in .env and --product-url not provided", file=sys.stderr)
        return 1

    print(f"Running pipeline for: {product_url[:80]}...", file=sys.stderr, flush=True)
    result = run_pipeline_v2(
        product_url,
        download_videos=not args.no_download,
        max_videos_to_download=5,
        max_videos_to_analyze=5,
    )

    content = result["report"] + "\n\n---\n\n# Generated Scripts\n\n" + result["scripts"]

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"Saved to {out.absolute()}", file=sys.stderr)
    else:
        print(content, end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
