"""
Video download and transcript extraction via yt-dlp.
Downloads videos from scraped links and extracts transcripts/scripts.
"""

import os
import subprocess
import tempfile
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


def download_video(
    url: str,
    output_dir: str | Path,
    *,
    max_duration_sec: int = 600,
    extract_transcript: bool = True,
) -> dict[str, Any]:
    """
    Download video via yt-dlp and optionally extract transcript.

    Args:
        url: Video URL (YouTube, TikTok, etc.).
        output_dir: Directory to save video and transcript.
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
    urls: list[str],
    output_dir: str | Path,
    *,
    max_per_video_sec: int = 600,
) -> list[dict[str, Any]]:
    """
    Download multiple videos and extract transcripts.
    Returns list of results (one per URL).
    """
    out_dir = Path(output_dir)
    results = []
    for url in urls:
        if not url or not url.strip():
            continue
        vid_dir = out_dir / _sanitize_url_for_dir(url)
        vid_dir.mkdir(parents=True, exist_ok=True)
        r = download_video(
            url,
            vid_dir,
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
