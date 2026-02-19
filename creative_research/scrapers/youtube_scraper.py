"""
YouTube Data API v3: search videos, detect Shorts, fetch comments.
"""

from creative_research.constants import YOUTUBE_OR_GOOGLE_API_KEY
from creative_research.scraped_data import VideoItem, CommentItem

SHORTS_MAX_DURATION_SEC = 60


def _get_api_key() -> str:
    if not YOUTUBE_OR_GOOGLE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY or GOOGLE_API_KEY is required. Set in .env")
    return YOUTUBE_OR_GOOGLE_API_KEY


def _parse_duration_seconds(iso: str) -> int:
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


def fetch_youtube_videos_and_comments(
    queries: list[str],
    *,
    max_videos: int = 20,
    max_comments_per_video: int = 20,
    product_link: str | None = None,
) -> tuple[list[VideoItem], list[VideoItem], list[CommentItem]]:
    """Search YouTube by query; split into long-form and Shorts; fetch comments."""
    from googleapiclient.discovery import build
    youtube = build("youtube", "v3", developerKey=_get_api_key())
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

    return long_form, shorts, comments
