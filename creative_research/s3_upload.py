"""
Upload files to S3 (Supabase Storage S3-compatible API).
"""
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _extract_video_id(url: str) -> str:
    """Extract platform-specific video ID from URL for S3 key."""
    # YouTube (watch, shorts, youtu.be)
    m = re.search(r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    if m:
        return m.group(1)
    # TikTok
    m = re.search(r"tiktok\.com.*?/video/(\d+)", url)
    if m:
        return m.group(1)
    # Instagram (reel, post, or explore/tags)
    m = re.search(r"instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"instagram\.com/explore/tags/([a-zA-Z0-9_]+)", url)
    if m:
        return m.group(1)
    # Fallback: sanitize URL tail
    return re.sub(r"[^\w\-]", "_", (url or "")[-50:]) or "video"


def upload_video_to_s3(
    local_path: str | Path,
    job_id: str,
    source_url: str,
    platform: str = "",
    *,
    bucket: str | None = None,
    prefix: str = "pipelines",
) -> str | None:
    """
    Upload a video file to S3 (Supabase Storage).
    Returns the S3 object key or full URL, or None on failure.

    S3 key: {prefix}/{job_id}/{platform}_{video_id}.mp4
    """
    path = Path(local_path)
    if not path.exists() or not path.is_file():
        logger.warning("upload_video_to_s3: file not found %s", local_path)
        return None

    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    bucket_name = bucket or os.environ.get("AWS_STORAGE_BUCKET_NAME")
    endpoint = os.environ.get("AWS_S3_ENDPOINT_URL")
    region = os.environ.get("AWS_S3_REGION_NAME", "ap-south-1")

    if not all([access_key, secret_key, bucket_name, endpoint]):
        logger.warning("upload_video_to_s3: missing AWS env vars")
        return None

    try:
        import boto3
        from botocore.config import Config

        video_id = _extract_video_id(source_url)
        ext = path.suffix.lower() or ".mp4"
        s3_key = f"{prefix}/{job_id}/{platform}_{video_id}{ext}".lstrip("_")

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

        content_type = "video/mp4" if ext in (".mp4",) else "video/webm" if ext in (".webm",) else "video/mp4"
        client.upload_file(
            str(path),
            bucket_name,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )

        # Return S3 path only (key), not full URL
        return s3_key
    except Exception as e:
        logger.exception("upload_video_to_s3 failed for %s: %s", local_path, e)
        return None


def get_video_meta_from_url(
    url: str,
    scraped_videos: list[dict[str, Any]],
) -> dict[str, Any]:
    """Get platform, title, views, etc. from scraped video list by URL."""
    url_norm = (url or "").strip()
    for v in scraped_videos:
        v_url = (v.get("url") or "").strip()
        if v_url and (v_url == url_norm or url_norm in v_url or v_url in url_norm):
            return v
    return {}


def extract_video_id(url: str) -> str:
    """Extract platform-specific video ID from URL."""
    return _extract_video_id(url)


def generate_presigned_url(
    s3_key: str,
    *,
    bucket: str | None = None,
    expires_in: int = 3600,
) -> str | None:
    """
    Generate a presigned URL for downloading an S3 object.
    Returns None if env vars are missing or generation fails.
    """
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    bucket_name = bucket or os.environ.get("AWS_STORAGE_BUCKET_NAME")
    endpoint = os.environ.get("AWS_S3_ENDPOINT_URL")
    region = os.environ.get("AWS_S3_REGION_NAME", "ap-south-1")

    if not all([access_key, secret_key, bucket_name, endpoint]) or not s3_key:
        return None

    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": s3_key},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        logger.warning("generate_presigned_url failed for %s: %s", s3_key, e)
        return None
