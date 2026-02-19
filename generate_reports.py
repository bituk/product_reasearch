#!/usr/bin/env python3
"""
Generate only report_popular.md and report_all_videos.md.

Runs the full pipeline and writes these two report files to the project root.
Uses PRODUCT_URL from .env.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from creative_research.constants import PRODUCT_URL
from creative_research.pipeline_v2 import run_pipeline_v2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate report_popular.md and report_all_videos.md (uses PRODUCT_URL from .env)"
    )
    parser.add_argument("--product-url", help="Override PRODUCT_URL from .env")
    parser.add_argument("-o", "--output-dir", default=".", help="Output directory (default: project root)")
    parser.add_argument("--no-download", action="store_true", help="Skip video download")
    parser.add_argument("--skip-apify", action="store_true", help="Skip Apify scrapers")
    args = parser.parse_args()

    if args.skip_apify:
        os.environ["SKIP_APIFY"] = "1"

    product_url = (args.product_url or PRODUCT_URL or "").strip()
    if not product_url:
        print("Error: PRODUCT_URL not set in .env and --product-url not provided", file=sys.stderr)
        return 1

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running pipeline for: {product_url[:80]}...", file=sys.stderr, flush=True)
    result = run_pipeline_v2(
        product_url,
        download_videos=not args.no_download,
        max_videos_total=20,
        max_videos_to_download=5,
        max_videos_to_analyze=5,
    )

    report_popular = result.get("report_popular", "")
    report_all_videos = result.get("report_all_videos", "")

    path_popular = out_dir / "report_popular.md"
    path_all = out_dir / "report_all_videos.md"

    path_popular.write_text(report_popular, encoding="utf-8")
    path_all.write_text(report_all_videos, encoding="utf-8")

    print(f"Saved {path_popular}", file=sys.stderr)
    print(f"Saved {path_all}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
