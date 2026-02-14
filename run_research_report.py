#!/usr/bin/env python3
"""
Standalone CLI for generating the Creative Agency Research Report.
Uses LLM only (no MCP); useful for scripts and CI.

Usage:
  python run_research_report.py "https://example.com/product"
  python run_research_report.py "https://..." --output report.md --model gpt-4o-mini
"""

import argparse
import sys
from pathlib import Path

# Allow running from repo root without installing package
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from creative_research.report_generator import generate_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Creative Agency Research Report from a product URL (LLM)."
    )
    parser.add_argument(
        "product_link",
        help="Full URL of the product (e.g. Amazon, brand site).",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        default=None,
        help="Path to save the report Markdown file. Default: print to stdout.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        help="OpenAI model (default: gpt-4o). Use gpt-4o-mini for faster/cheaper runs.",
    )
    parser.add_argument(
        "--content-file",
        dest="content_file",
        default=None,
        help="Optional path to a file with pre-fetched product page text (skip fetch).",
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Run Apify + YouTube + Reddit scrapers (requires API keys in .env), then use scraped data in report.",
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        default=[],
        help="Search queries / hashtags for --scrape (e.g. skincare anti-aging).",
    )
    parser.add_argument(
        "--subreddits",
        nargs="+",
        default=[],
        help="Subreddits for --scrape (e.g. SkincareAddiction).",
    )
    args = parser.parse_args()

    product_page_content = None
    scraped_data = None
    if args.content_file:
        path = Path(args.content_file)
        if not path.exists():
            print(f"Error: content file not found: {path}", file=sys.stderr)
            return 1
        product_page_content = path.read_text(encoding="utf-8")
    elif args.scrape:
        from creative_research.scrapers.runner import run_all_scrapes
        q = args.queries or ["product review", "best"]
        print("Running scrapers...", file=sys.stderr, flush=True)
        scraped_data = run_all_scrapes(args.product_link, search_queries=q, subreddits=args.subreddits)
        print("Scrape done.", file=sys.stderr, flush=True)

    try:
        report = generate_report(
            args.product_link,
            product_page_content=product_page_content,
            scraped_data=scraped_data,
            model=args.model,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        return 1

    if args.output_path:
        out = Path(args.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"Report saved to {out} ({len(report)} characters).", file=sys.stderr)
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
