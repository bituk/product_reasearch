"""
Apify-based scrapers for TikTok, Instagram, Amazon.
Requires APIFY_API_TOKEN in env. Uses official Apify actors.
"""

import dataclasses
from typing import Any

from creative_research.scraped_data import ScrapedData, VideoItem, CommentItem
from creative_research.constants import APIFY_API_TOKEN, APIFY_AMAZON_ACTOR_ID

# Apify actor IDs (from apify.com store). Override via env if needed.
ACTOR_TIKTOK_HASHTAG = "clockworks/tiktok-hashtag-scraper"
ACTOR_INSTAGRAM_HASHTAG = "apify/instagram-hashtag-scraper"
ACTOR_AMAZON_PRODUCT = APIFY_AMAZON_ACTOR_ID  # ASIN/URL → product + reviews


def _get_client():
    token = APIFY_API_TOKEN
    if not token:
        raise ValueError("APIFY_API_TOKEN is required for Apify scrapes. Set it in .env")
    try:
        from apify_client import ApifyClient
        return ApifyClient(token=token)
    except ImportError:
        raise ImportError("Install apify-client: pip install apify-client")
    except Exception as e:
        raise RuntimeError(f"Apify client init failed: {e}") from e


def _run_actor(
    client, actor_id: str, run_input: dict, timeout_secs: int = 120, product_link: str | None = None
) -> list[dict]:
    """Run an Apify actor and return dataset items."""
    try:
        run = client.actor(actor_id).call(run_input=run_input, timeout_secs=timeout_secs)
        store_id = run.get("defaultDatasetId")
        if not store_id:
            return []
        return list(client.dataset(store_id).iterate_items())
    except Exception:
        return []


def run_apify_tiktok(
    queries: list[str],
    max_results: int = 20,
    product_link: str | None = None,
    *,
    should_download_videos: bool = False,
) -> list[VideoItem]:
    """Scrape TikTok by hashtag/search. Returns list of VideoItem.
    If should_download_videos=True, Apify downloads videos to its storage (higher cost, slower).
    """
    client = _get_client()
    items: list[VideoItem] = []
    for q in queries[:3]:  # Limit to 3 queries to stay within free tier
        # When downloading videos, limit to 8 per hashtag (Apify cost); otherwise up to 30
        per_page = min(8, max_results) if should_download_videos else min(max_results, 30)
        run_input = {
            "hashtags": [q.replace("#", "").strip()],
            "resultsPerPage": per_page,
            "shouldDownloadVideos": should_download_videos,
        }
        raw = _run_actor(
            client,
            ACTOR_TIKTOK_HASHTAG,
            run_input,
            timeout_secs=120 if should_download_videos else 90,
        )
        for r in raw:
            # webVideoUrl may be wrapped in angle brackets by Apify: "<https://...>"
            tiktok_url = (r.get("webVideoUrl") or r.get("videoUrl") or "").strip().strip("<>")
            if not tiktok_url:
                continue
            if not tiktok_url.startswith("http"):
                tiktok_url = f"https://www.tiktok.com/{tiktok_url}" if tiktok_url.startswith("@") else ""
            if not tiktok_url.startswith("http"):
                continue
            # Direct video URL: Apify storage (when shouldDownloadVideos), CDN (v16-webapp), or .mp4
            tiktok_direct = ""
            media_urls = r.get("mediaUrls") or []
            for m in media_urls:
                u = (m if isinstance(m, str) else "").strip().strip("<>")
                if u and (".mp4" in u or "v16-webapp" in u or "tiktokv" in u or "api.apify.com" in u):
                    tiktok_direct = u
                    break
            if not tiktok_direct:
                vm = r.get("videoMeta") or {}
                for k in ("downloadAddr", "originalDownloadAddr"):
                    u = (vm.get(k) or "").strip().strip("<>")
                    if u and (".mp4" in u or "v16-webapp" in u or "tiktokv" in u or "api.apify.com" in u):
                        tiktok_direct = u
                        break
            items.append(VideoItem(
                platform="TikTok",
                title=r.get("text") or r.get("desc") or "",
                url=tiktok_url,
                video_direct_url=tiktok_direct,
                description=r.get("text", "")[:500],
                views=r.get("playCount") or 0,
                likes=r.get("diggCount") or 0,
                comments_count=r.get("commentCount") or 0,
                shares=r.get("shareCount") or r.get("collectCount") or 0,
                author=r.get("authorMeta", {}).get("name", ""),
                raw=r,
            ))
    return items[:max_results]


def run_apify_instagram(
    queries: list[str], max_results: int = 20, product_link: str | None = None
) -> list[VideoItem]:
    """Scrape Instagram Reels/posts by hashtag."""
    client = _get_client()
    items: list[VideoItem] = []
    for q in queries[:3]:
        raw = _run_actor(
            client,
            ACTOR_INSTAGRAM_HASHTAG,
            {"hashtags": [q.replace("#", "").strip()], "resultsLimit": min(max_results, 30)},
            timeout_secs=90,
        )
        for r in raw:
            caption = (r.get("caption") or "")[:500]
            page_url = r.get("url") or ""
            if not page_url and r.get("shortCode"):
                # Build URL from shortCode (reel vs post)
                sc = r.get("shortCode", "")
                page_url = f"https://www.instagram.com/reel/{sc}/" if r.get("type") == "Video" else f"https://www.instagram.com/p/{sc}/"
            video_direct = r.get("videoUrl", "") if r.get("type") == "Video" else ""
            items.append(VideoItem(
                platform="Instagram",
                title=caption or "Instagram post",
                url=page_url,
                video_direct_url=video_direct,
                description=caption,
                views=r.get("videoViewCount") or r.get("likesCount") or 0,
                likes=r.get("likesCount") or 0,
                comments_count=r.get("commentsCount") or 0,
                shares=r.get("videoPlayCount") or 0,
                author=r.get("ownerUsername", ""),
                raw=r,
            ))
    return items[:max_results]


def run_apify_amazon(product_url: str) -> list[dict]:
    """Scrape Amazon product page (reviews, title, etc.). Returns raw items for LLM."""
    client = _get_client()
    actor = ACTOR_AMAZON_PRODUCT
    run_input = {"startUrls": [{"url": product_url}]}
    raw = _run_actor(client, actor, run_input, timeout_secs=120, product_link=product_url.strip())
    return raw


def run_apify_scrapes(
    product_url: str,
    search_hashtags: list[str],
    *,
    max_videos_per_platform: int = 15,
    tiktok_download_videos: bool = True,
) -> tuple[list[VideoItem], list[VideoItem], list[dict], list[dict], list[dict]]:
    """
    Run TikTok, Instagram, and Amazon scrapes via Apify.
    When tiktok_download_videos=True, Apify downloads TikTok videos to its storage (enables direct download).
    Returns (tiktok_videos, instagram_videos, amazon_raw, apify_tiktok_raw, apify_instagram_raw).
    """
    tiktok = run_apify_tiktok(
        search_hashtags,
        max_results=max_videos_per_platform,
        product_link=product_url,
        should_download_videos=tiktok_download_videos,
    )
    instagram = run_apify_instagram(
        search_hashtags, max_results=max_videos_per_platform, product_link=product_url
    )
    amazon_raw = run_apify_amazon(product_url) if "amazon" in product_url.lower() else []
    apify_tiktok_raw = [v.raw for v in tiktok[:20]]
    apify_instagram_raw = [v.raw for v in instagram[:20]]
    return tiktok, instagram, amazon_raw, apify_tiktok_raw, apify_instagram_raw
