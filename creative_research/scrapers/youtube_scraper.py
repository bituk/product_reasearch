"""
YouTube Data API v3: search videos, detect Shorts, fetch comments.
Free quota: 10,000 units/day. Successful responses cached (CREATIVE_RESEARCH_NO_CACHE=1 to disable).
"""

import dataclasses
import os
from typing import Any

from creative_research.scraped_data import VideoItem, CommentItem
from creative_research.cache import load_cached, save_cached

# Shorts are typically <= 60 seconds
SHORTS_MAX_DURATION_SEC = 60


def _get_api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise ValueError("YOUTUBE_API_KEY or GOOGLE_API_KEY is required for YouTube scrapes. Set in .env")
    return key


def _build_youtube():
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=_get_api_key())


def _parse_duration_seconds(iso: str) -> int:
    """Parse YouTube duration (e.g. PT1M30S) to seconds."""
    if not iso:
        return 0
    import re
    total = 0
    for match in re.finditer(r"(\d+)([HMS])", iso):
        n, u = int(match.group(1)), match.group(2)
        if u == "H":
            total += n * 3600
        elif u == "M":
            total += n * 60
        else:
            total += n
    return total


def _serialize_yt_result(long_form: list, shorts: list, comments: list) -> dict:
    return {
        "long_form": [dataclasses.asdict(v) for v in long_form],
        "shorts": [dataclasses.asdict(v) for v in shorts],
        "comments": [dataclasses.asdict(v) for v in comments],
    }


def _deserialize_yt_result(data: dict) -> tuple[list[VideoItem], list[VideoItem], list[CommentItem]]:
    long_form = [VideoItem(**d) for d in data.get("long_form", [])]
    shorts = [VideoItem(**d) for d in data.get("shorts", [])]
    comments = [CommentItem(**d) for d in data.get("comments", [])]
    return long_form, shorts, comments


def fetch_youtube_videos_and_comments(
    queries: list[str],
    *,
    max_videos: int = 20,
    max_comments_per_video: int = 20,
    product_link: str | None = None,
) -> tuple[list[VideoItem], list[VideoItem], list[CommentItem]]:
    """
    Search YouTube by query; split into long-form and Shorts; fetch comments for first N videos.
    Returns (long_form_videos, shorts_videos, comments). Uses cache on hit (keyed by product_link).
    """
    cache_key = (product_link or "").strip() or "_"
    cached, hit = load_cached("youtube", product_link=cache_key)
    if hit and isinstance(cached, dict) and "long_form" in cached:
        return _deserialize_yt_result(cached)

    youtube = _build_youtube()
    all_video_ids: list[str] = []
    video_details: dict[str, dict] = {}

    for q in queries[:5]:
        req = youtube.search().list(
            part="id,snippet",
            q=q,
            type="video",
            maxResults=min(25, max_videos),
            order="viewCount",
        )
        res = req.execute()
        for item in res.get("items", []):
            vid = item.get("id", {}).get("videoId")
            if vid and vid not in video_details:
                all_video_ids.append(vid)
                video_details[vid] = {"snippet": item.get("snippet", {})}

    if not all_video_ids:
        return [], [], []

    # Get duration and stats (videos.list)
    for i in range(0, len(all_video_ids), 50):
        chunk = all_video_ids[i : i + 50]
        req = youtube.videos().list(
            part="contentDetails,statistics,snippet",
            id=",".join(chunk),
        )
        res = req.execute()
        for item in res.get("items", []):
            vid = item["id"]
            if vid in video_details:
                video_details[vid].update(item)

    long_form: list[VideoItem] = []
    shorts: list[VideoItem] = []
    for vid, det in list(video_details.items())[:max_videos]:
        snippet = det.get("snippet", {})
        stats = det.get("statistics", {})
        dur_iso = (det.get("contentDetails") or {}).get("duration", "")
        dur_sec = _parse_duration_seconds(dur_iso)
        title = snippet.get("title", "")
        url = f"https://www.youtube.com/watch?v={vid}"
        v = VideoItem(
            platform="YouTube",
            title=title,
            url=url,
            description=(snippet.get("description") or "")[:500],
            views=int(stats.get("viewCount") or 0),
            likes=int(stats.get("likeCount") or 0),
            comments_count=int(stats.get("commentCount") or 0),
            published_at=snippet.get("publishedAt", ""),
            author=snippet.get("channelTitle", ""),
            raw=det,
        )
        if dur_sec > 0 and dur_sec <= SHORTS_MAX_DURATION_SEC:
            shorts.append(v)
        else:
            long_form.append(v)

    # Comments from first few videos (quota-friendly)
    comments: list[CommentItem] = []
    for v in (long_form + shorts)[:5]:
        try:
            req = youtube.commentThreads().list(
                part="snippet",
                videoId=v.url.split("v=")[-1].split("&")[0],
                maxResults=max_comments_per_video,
                textFormat="plainText",
            )
            res = req.execute()
            for thread in res.get("items", []):
                top = (thread.get("snippet") or {}).get("topLevelComment", {}).get("snippet", {})
                comments.append(CommentItem(
                    source="youtube",
                    text=top.get("textDisplay") or top.get("textOriginal", ""),
                    author=top.get("authorDisplayName", ""),
                    likes=top.get("likeCount", 0),
                    created_at=top.get("publishedAt", ""),
                    raw=thread,
                ))
        except Exception:
            continue

    if long_form or shorts or comments:
        save_cached("youtube", _serialize_yt_result(long_form, shorts, comments), product_link=cache_key)
    return long_form, shorts, comments
