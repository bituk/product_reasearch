"""
Video download and transcript extraction via yt-dlp.
Downloads videos from scraped links (YouTube, TikTok, Instagram) and extracts transcripts/scripts.
Supports direct CDN URLs from Apify (Instagram videoUrl) for faster downloads.
"""

import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

# Optional: youtube-transcript-api as fallback when yt-dlp subs unavailable
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    HAS_YOUTUBE_TRANSCRIPT = True
except ImportError:
    HAS_YOUTUBE_TRANSCRIPT = False


def _get_yt_dlp_path() -> str:
    """Ensure yt-dlp is available (cli or python -m yt_dlp)."""
    try:
        import yt_dlp
        return "python"
    except ImportError:
        pass
    # Prefer yt-dlp CLI if installed
    if subprocess.run(["which", "yt-dlp"], capture_output=True).returncode == 0:
        return "yt-dlp"
    raise ImportError(
        "yt-dlp is required for video download. Install: pip install yt-dlp"
    )


def extract_transcript_yt_dlp(url: str, output_dir: str | Path | None = None) -> str | None:
    """
    Extract transcript/subtitles using yt-dlp.
    Returns transcript text or None if unavailable.
    """
    out_dir = Path(output_dir or tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "subs.%(ext)s")

    try:
        import yt_dlp
        ydl_opts = {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitlesformat": "vtt/best",
            "skip_download": True,
            "outtmpl": out_template.replace("%(ext)s", "vtt"),
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None
    except Exception:
        return _extract_transcript_fallback(url)


def _extract_transcript_fallback(url: str) -> str | None:
    """Fallback: youtube-transcript-api for YouTube URLs only."""
    if not HAS_YOUTUBE_TRANSCRIPT:
        return None
    try:
        video_id = _extract_youtube_id(url)
        if not video_id:
            return None
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(t["text"] for t in transcript_list)
    except Exception:
        return None


def _extract_youtube_id(url: str) -> str | None:
    import re
    m = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else None


def _download_direct_video(url: str, output_path: Path) -> bool:
    """Download video from direct URL (e.g. Instagram CDN from Apify). Returns True if success."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; VideoDownloader/1.0)"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            output_path.write_bytes(resp.read())
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception:
        return False


def download_video(
    url: str,
    output_dir: str | Path,
    *,
    video_direct_url: str | None = None,
    max_duration_sec: int = 600,
    extract_transcript: bool = True,
) -> dict[str, Any]:
    """
    Download video via yt-dlp or direct download (for Apify CDN URLs).

    Args:
        url: Video page URL (YouTube, TikTok, Instagram) or identifier.
        output_dir: Directory to save video and transcript.
        video_direct_url: Optional direct CDN URL (from Apify Instagram videoUrl) for fast download.
        max_duration_sec: Skip videos longer than this (default 10 min).
        extract_transcript: If True, also extract transcript/script.

    Returns:
        {
            "success": bool,
            "video_path": str | None,
            "transcript": str | None,
            "duration_sec": float | None,
            "error": str | None,
        }
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "%(id)s")

    result: dict[str, Any] = {
        "success": False,
        "video_path": None,
        "transcript": None,
        "duration_sec": None,
        "error": None,
    }

    # Try direct download first when we have Apify CDN URL (Instagram, TikTok)
    if video_direct_url and (
        ".mp4" in video_direct_url
        or "cdninstagram" in video_direct_url
        or "tiktok" in video_direct_url.lower()
    ):
        import re
        vid_id = _extract_youtube_id(url) or re.sub(r"[^\w\-]", "_", (url or "")[-60:]) or "video"
        out_path = out_dir / f"{vid_id}.mp4"
        if _download_direct_video(video_direct_url, out_path):
            result["success"] = True
            result["video_path"] = str(out_path.absolute())
            # No transcript from direct download; try yt-dlp for transcript only if we have page URL
            if extract_transcript and ("instagram.com" in url):
                try:
                    transcript = extract_transcript_yt_dlp(url, out_dir)
                    result["transcript"] = transcript
                except Exception:
                    pass
            return result

    try:
        import yt_dlp
        def _duration_filter(info, *, incomplete=False):
            dur = info.get("duration")
            if dur and dur > max_duration_sec:
                return f"Video too long ({dur}s > {max_duration_sec}s)"

        ydl_opts = {
            "outtmpl": out_template,
            "format": "best[ext=mp4]/best",
            "quiet": False,
            "no_warnings": True,
            "match_filter": _duration_filter,
        }
        # Platform-specific options for TikTok and Instagram
        if "tiktok.com" in url:
            ydl_opts.setdefault("extractor_args", {})["tiktok"] = {"format": "best"}
        if "instagram.com" in url:
            ydl_opts.setdefault("extractor_args", {})["instagram"] = {"format": "best"}
        if extract_transcript:
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = True
            ydl_opts["subtitlesformat"] = "vtt/best"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            err_str = str(e)
            # HTTP 429 (Too Many Requests) on subtitles - retry without subtitles
            if ("429" in err_str or "Too Many Requests" in err_str) and extract_transcript:
                ydl_opts_no_subs = {
                    "outtmpl": out_template,
                    "format": "best[ext=mp4]/best",
                    "quiet": False,
                    "no_warnings": True,
                    "match_filter": _duration_filter,
                }
                with yt_dlp.YoutubeDL(ydl_opts_no_subs) as ydl:
                    info = ydl.extract_info(url, download=True)
            else:
                raise

        if not info:
            result["error"] = "Could not extract video info"
            return result

        result["duration_sec"] = info.get("duration")
        result["success"] = True

        # Find downloaded file (yt-dlp saves to outtmpl path)
        vid_id = info.get("id", "unknown")
        candidates = list(out_dir.glob(f"{vid_id}.*")) + list(out_dir.glob("*.*"))
        for p in candidates:
            if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov") and p.exists():
                result["video_path"] = str(p.absolute())
                break

        # Transcript from subtitle file or fallback (youtube-transcript-api for 429/YouTube)
        if extract_transcript:
            sub_files = list(out_dir.glob("*.vtt"))
            if sub_files:
                result["transcript"] = _parse_vtt_to_text(sub_files[0])
            if not result["transcript"] and "youtube" in url.lower():
                result["transcript"] = _extract_transcript_fallback(url)

    except Exception as e:
        result["error"] = str(e)

    return result


def _parse_vtt_to_text(vtt_path: Path) -> str:
    """Parse VTT subtitle file to plain text."""
    import re
    text = vtt_path.read_text(encoding="utf-8", errors="ignore")
    # Remove VTT header (WEBVTT, etc.)
    text = re.sub(r"^WEBVTT.*?\n", "", text, flags=re.IGNORECASE)
    # Remove cue timestamps (00:00:00.000 --> 00:00:01.000)
    text = re.sub(r"\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}.*?\n", "", text)
    text = re.sub(r"^\d+\n", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def download_and_transcript_batch(
    urls: list[str] | list[dict[str, Any]],
    output_dir: str | Path,
    *,
    max_per_video_sec: int = 600,
) -> list[dict[str, Any]]:
    """
    Download multiple videos and extract transcripts.
    Accepts list of URLs (str) or list of dicts with "url" and optional "video_direct_url".
    Returns list of results (one per URL).
    """
    out_dir = Path(output_dir)
    results = []
    for item in urls:
        if isinstance(item, dict):
            url = item.get("url", "")
            video_direct_url = item.get("video_direct_url") or ""
        else:
            url = str(item) if item else ""
            video_direct_url = ""
        if not url or not url.strip():
            continue
        vid_dir = out_dir / _sanitize_url_for_dir(url)
        vid_dir.mkdir(parents=True, exist_ok=True)
        r = download_video(
            url,
            vid_dir,
            video_direct_url=video_direct_url or None,
            max_duration_sec=max_per_video_sec,
            extract_transcript=True,
        )
        r["url"] = url
        results.append(r)
    return results


def _sanitize_url_for_dir(url: str) -> str:
    import re
    vid_id = _extract_youtube_id(url) or re.sub(r"[^\w\-]", "_", url[:50])
    return f"vid_{vid_id}"
