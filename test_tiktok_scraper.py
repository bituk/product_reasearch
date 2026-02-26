#!/usr/bin/env python3
"""
Test TikTok scraper via Apify.
Verifies that run_apify_tiktok returns valid videos with URLs and metadata.
Download uses direct URL when available, yt-dlp as fallback when not.

Usage:
  python3 test_tiktok_scraper.py [--download] [--hashtag HASHTAG]

Requires: APIFY_API_TOKEN in .env
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


def test_tiktok_scrape(hashtag: str = "productreview", max_results: int = 5) -> bool:
    """Scrape TikTok videos via Apify and verify structure."""
    from creative_research.scrapers.apify_scraper import run_apify_tiktok

    print(f"\n--- TikTok scrape (hashtag: #{hashtag}, max_results={max_results}) ---")
    videos = run_apify_tiktok([hashtag], max_results=max_results, should_download_videos=False)
    if not videos:
        videos = run_apify_tiktok([hashtag], max_results=max_results, should_download_videos=True)

    if not videos:
        print("  FAIL: No TikTok videos returned")
        print("  Tip: Try a different hashtag (e.g. --hashtag perfume)")
        return False

    print(f"  OK: Got {len(videos)} TikTok video(s)")
    for i, v in enumerate(videos, 1):
        has_url = bool(v.url and v.url.startswith("http"))
        has_direct = bool(v.video_direct_url)
        print(f"    [{i}] url={has_url} ({v.url[:60] if v.url else 'N/A'}...)")
        print(f"        video_direct_url={has_direct} ({v.video_direct_url[:70] + '...' if v.video_direct_url else 'None'})")
        print(f"        views={v.views}, likes={v.likes}, author={v.author or 'N/A'}")
        if not has_url:
            print("  FAIL: Invalid or missing page URL")
            return False

    return True


def test_tiktok_download(hashtag: str = "productreview") -> bool:
    """Download one TikTok video. Uses direct URL when available, yt-dlp as fallback."""
    from creative_research.scrapers.apify_scraper import run_apify_tiktok
    from creative_research.video_downloader import download_video

    out_dir = Path(__file__).parent / "downloads" / "test_tiktok"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Download test (hashtag: #{hashtag}) ---")
    videos = run_apify_tiktok([hashtag], max_results=5, should_download_videos=False)
    if not videos:
        videos = run_apify_tiktok([hashtag], max_results=5, should_download_videos=True)

    if not videos:
        print("  SKIP: No TikTok videos returned")
        return True

    # Try first video (with or without direct URL — yt-dlp fallback when no direct)
    v = videos[0]
    has_direct = bool(v.video_direct_url)
    print(f"  Using first video: url={v.url[:50]}..., direct_url={'yes' if has_direct else 'no (yt-dlp fallback)'}")
    r = download_video(v.url, out_dir, video_direct_url=v.video_direct_url or None)
    if r.get("success"):
        size = Path(r["video_path"]).stat().st_size if r.get("video_path") else 0
        print(f"  OK: Downloaded {r.get('video_path', '')} ({size:,} bytes)")
        return True
    else:
        print(f"  FAIL: {r.get('error', 'Unknown error')}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test TikTok scraper via Apify")
    parser.add_argument("--hashtag", default="productreview", help="Hashtag to scrape (default: productreview)")
    parser.add_argument("--max", type=int, default=5, help="Max results (default: 5)")
    parser.add_argument("--download", action="store_true", help="Also test video download")
    args = parser.parse_args()

    if not os.environ.get("APIFY_API_TOKEN"):
        print("Error: APIFY_API_TOKEN not set in .env")
        return 1

    print("=" * 60)
    print("TikTok Scraper Test (Apify)")
    print("=" * 60)

    ok = test_tiktok_scrape(hashtag=args.hashtag, max_results=args.max)
    if ok and args.download:
        ok &= test_tiktok_download(hashtag=args.hashtag)

    print("\n" + "=" * 60)
    print("PASS" if ok else "FAIL")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
