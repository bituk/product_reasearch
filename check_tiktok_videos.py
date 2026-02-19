#!/usr/bin/env python3
"""
Check which videos are from TikTok when scraping with a product URL.
Runs keywords + Apify scrapes, then lists TikTok videos found.

Usage:
  python3 check_tiktok_videos.py
  python3 check_tiktok_videos.py --product-url "https://www.amazon.com/product/..."
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


def main():
    from creative_research.constants import PRODUCT_URL
    from creative_research.report_generator import fetch_product_page
    from creative_research.keyword_generator import generate_keywords
    from creative_research.scrapers.runner import run_all_scrapes

    parser = argparse.ArgumentParser(description="Check TikTok videos for a product URL")
    parser.add_argument("--product-url", help="Product URL (default: PRODUCT_URL from .env)")
    parser.add_argument("--quick", action="store_true", help="Use hashtag 'productreview' only (skip keywords, faster)")
    args = parser.parse_args()

    product_url = (args.product_url or os.environ.get("PRODUCT_URL") or "").strip()
    if not product_url:
        print("Error: Provide --product-url or set PRODUCT_URL in .env")
        return 1

    print(f"Product URL: {product_url[:80]}...")
    print("=" * 60)

    if args.quick:
        queries = ["productreview"]
        product_page_text = ""
        print("Quick mode: using hashtag 'productreview'")
    else:
        product_page_text = ""
        try:
            product_page_text = fetch_product_page(product_url)
            print(f"Fetched product page: {len(product_page_text)} chars")
        except Exception as e:
            print(f"Could not fetch product page: {e}")

        try:
            keywords = generate_keywords(product_url, product_page_text)
            queries = keywords.get("search_queries", []) or ["productreview"]
            print(f"Search queries: {queries[:5]}")
        except Exception as e:
            print(f"Keywords failed: {e}")
            queries = ["productreview"]

    # Run scrapes (all four: YouTube, Shorts, TikTok, Instagram)
    print("\nScraping (YouTube, Shorts, TikTok, Instagram)...")
    scraped = run_all_scrapes(
        product_url,
        search_queries=queries,
        subreddits=["all"],
        product_page_text=product_page_text or None,
        tiktok_download_videos=True,
        apify_only=False,
    )

    # List TikTok videos
    tiktok = scraped.tiktok_videos
    print("\n" + "=" * 60)
    print(f"TikTok videos: {len(tiktok)}")
    print("=" * 60)

    if not tiktok:
        print("No TikTok videos found.")
        return 0

    for i, v in enumerate(tiktok, 1):
        has_direct = bool(v.video_direct_url)
        print(f"\n[{i}] {v.title[:50] if v.title else 'N/A'}...")
        print(f"    URL: {v.url}")
        print(f"    video_direct_url: {'Yes' if has_direct else 'No'}")
        print(f"    Views: {v.views:,} | Likes: {v.likes:,} | Author: {v.author}")

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  YouTube: {len(scraped.youtube_videos)}")
    print(f"  YouTube Shorts: {len(scraped.youtube_shorts)}")
    print(f"  TikTok: {len(tiktok)}")
    print(f"  Instagram: {len(scraped.instagram_videos)}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
