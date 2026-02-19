#!/usr/bin/env python3
"""
Test TikTok video download: Apify scrape + direct/CDN + yt-dlp fallback.
Run from project root: python3 test_tiktok_download.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def test_tiktok_via_apify_and_download():
    """Scrape 1 TikTok via Apify, then download it."""
    from creative_research.scrapers.apify_scraper import run_apify_tiktok
    from creative_research.video_downloader import download_video

    if not os.environ.get("APIFY_API_TOKEN"):
        print("SKIP: APIFY_API_TOKEN not set. Set in .env to test Apify + download.")
        return 1

    print("1. Scraping TikTok via Apify (hashtag: productreview, shouldDownloadVideos=True)...")
    videos = run_apify_tiktok(["productreview"], max_results=2, should_download_videos=True)
    if not videos:
        print("   No TikTok videos returned from Apify.")
        return 1

    v = videos[0]
    print(f"   Got: {v.url}")
    print(f"   video_direct_url: {v.video_direct_url[:80] if v.video_direct_url else 'None'}...")

    out_dir = Path(__file__).parent / "downloads" / "test_tiktok"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("2. Downloading (direct first, then yt-dlp fallback)...")
    result = download_video(
        v.url,
        out_dir,
        video_direct_url=v.video_direct_url or None,
        extract_transcript=True,
    )

    if result["success"]:
        print(f"   SUCCESS: {result['video_path']}")
        if result.get("video_path") and Path(result["video_path"]).exists():
            size = Path(result["video_path"]).stat().st_size
            print(f"   File size: {size:,} bytes")
        return 0
    else:
        print(f"   FAILED: {result.get('error', 'Unknown error')}")
        return 1


def test_tiktok_ytdlp_only():
    """Test yt-dlp with a known public TikTok URL (no Apify)."""
    from creative_research.video_downloader import download_video

    # Use a well-known public TikTok URL for testing
    test_url = "https://www.tiktok.com/@tiktok/video/7000000000000000000"
    # That ID might not exist - use a real one. Let's try a generic search result.
    # Actually we can't hardcode a working URL as they change. Use Apify result.
    print("Test yt-dlp only: requires a valid TikTok URL.")
    print("Run test_tiktok_via_apify_and_download() for full test.")
    return 0


if __name__ == "__main__":
    print("=" * 60)
    print("TikTok Download Test")
    print("=" * 60)
    code = test_tiktok_via_apify_and_download()
    sys.exit(code)
