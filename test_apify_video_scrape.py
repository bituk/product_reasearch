#!/usr/bin/env python3
"""
Test Apify video scraping: TikTok and Instagram only.
Scrapes videos via Apify, verifies structure, and tests download.

Usage:
  python3 test_apify_video_scrape.py

Requires: APIFY_API_TOKEN in .env
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


def test_tiktok_scrape():
    """Scrape TikTok videos via Apify (with download for direct URL)."""
    from creative_research.scrapers.apify_scraper import run_apify_tiktok

    hashtags = ["productreview"]
    print("\n--- TikTok scrape (hashtag: productreview, shouldDownloadVideos=True) ---")
    videos = run_apify_tiktok(hashtags, max_results=3, should_download_videos=True)

    if not videos:
        print("  FAIL: No TikTok videos returned")
        return False

    print(f"  OK: Got {len(videos)} TikTok video(s)")
    for i, v in enumerate(videos[:3], 1):
        has_url = bool(v.url and v.url.startswith("http"))
        has_direct = bool(v.video_direct_url)
        print(f"    [{i}] url={has_url} ({v.url[:50] if v.url else 'N/A'}...)")
        print(f"        video_direct_url={has_direct} ({v.video_direct_url[:60] if v.video_direct_url else 'None'}...)")
        print(f"        views={v.views}, likes={v.likes}")
        if not has_url:
            print("  FAIL: Invalid or missing page URL")
            return False

    return True


def test_instagram_scrape():
    """Scrape Instagram videos via Apify."""
    from creative_research.scrapers.apify_scraper import run_apify_instagram

    hashtags = ["productreview"]
    print("\n--- Instagram scrape (hashtag: productreview) ---")
    videos = run_apify_instagram(hashtags, max_results=3)

    if not videos:
        print("  FAIL: No Instagram videos returned")
        return False

    print(f"  OK: Got {len(videos)} Instagram video(s)")
    for i, v in enumerate(videos[:3], 1):
        has_url = bool(v.url and ("instagram.com" in v.url))
        has_direct = bool(v.video_direct_url)
        print(f"    [{i}] url={has_url} ({v.url[:50] if v.url else 'N/A'}...)")
        print(f"        video_direct_url={has_direct} ({v.video_direct_url[:60] if v.video_direct_url else 'None'}...)")
        print(f"        views={v.views}, likes={v.likes}")
        if not has_url:
            print("  FAIL: Invalid or missing page URL")
            return False

    return True


def test_download_sample():
    """Download one TikTok and one Instagram video to verify."""
    from creative_research.scrapers.apify_scraper import run_apify_tiktok, run_apify_instagram
    from creative_research.video_downloader import download_video

    out_dir = Path(__file__).parent / "downloads" / "test_apify_scrape"
    out_dir.mkdir(parents=True, exist_ok=True)

    # TikTok
    print("\n--- Download test: TikTok ---")
    tiktok = run_apify_tiktok(["productreview"], max_results=1, should_download_videos=True)
    if tiktok:
        v = tiktok[0]
        r = download_video(v.url, out_dir / "tiktok", video_direct_url=v.video_direct_url or None)
        if r["success"]:
            print(f"  OK: Downloaded {r['video_path']} ({Path(r['video_path']).stat().st_size:,} bytes)")
        else:
            print(f"  FAIL: {r.get('error', 'Unknown error')}")
            return False
    else:
        print("  SKIP: No TikTok videos to download")

    # Instagram (Apify returns videoUrl only for type=Video; posts may be images)
    print("\n--- Download test: Instagram ---")
    insta = run_apify_instagram(["productreview"], max_results=5)
    insta_videos = [v for v in insta if v.video_direct_url]
    if insta_videos:
        v = insta_videos[0]
        r = download_video(v.url, out_dir / "instagram", video_direct_url=v.video_direct_url or None)
        if r["success"]:
            print(f"  OK: Downloaded {r['video_path']} ({Path(r['video_path']).stat().st_size:,} bytes)")
        else:
            print(f"  FAIL: {r.get('error', 'Unknown error')}")
            return False
    else:
        print("  SKIP: No Instagram Video posts (Apify may return images; videoUrl only for type=Video)")

    return True


def main():
    if not os.environ.get("APIFY_API_TOKEN"):
        print("Error: APIFY_API_TOKEN not set in .env")
        return 1

    print("=" * 60)
    print("Apify Video Scrape Test (TikTok + Instagram)")
    print("=" * 60)

    ok = True
    ok &= test_tiktok_scrape()
    ok &= test_instagram_scrape()

    if ok:
        print("\n--- Download verification (optional) ---")
        ok &= test_download_sample()

    print("\n" + "=" * 60)
    print("PASS" if ok else "FAIL")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
