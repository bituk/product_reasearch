"""
Cache pipeline: runs full pipeline, keeps downloads on disk, uploads to S3 and saves PipelineVideo.
Use until main pipeline S3/DB upload is fixed.
"""
import logging
import os
import re
from pathlib import Path

from django.utils import timezone

logger = logging.getLogger(__name__)

_project_root = Path(__file__).resolve().parent.parent.parent


def upload_videos_from_cache(job_id: str) -> dict:
    """
    Upload cached videos to S3 and create PipelineVideo records.
    Reads from job's stored data (download_results, full_result) and scans output_dir for files.
    Returns {uploaded: int, failed: int, errors: list}.
    """
    from pipeline_jobs.models import PipelineJob, PipelineVideo

    result = {"uploaded": 0, "failed": 0, "errors": []}

    try:
        job = PipelineJob.objects.get(pk=job_id)
    except PipelineJob.DoesNotExist:
        result["errors"].append("Job not found")
        return result

    output_dir_str = (job.metadata or {}).get("cache_output_dir")
    if output_dir_str:
        output_dir = Path(output_dir_str)
    else:
        output_dir = _project_root / "downloads" / "videos" / str(job_id)
    if not output_dir.exists():
        result["errors"].append(f"Cache dir not found: {output_dir}")
        return result

    # Load .env
    _env_path = _project_root / ".env"
    if _env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(_env_path)
        except ImportError:
            pass

    if not all([
        os.environ.get("AWS_ACCESS_KEY_ID"),
        os.environ.get("AWS_SECRET_ACCESS_KEY"),
        os.environ.get("AWS_STORAGE_BUCKET_NAME"),
        os.environ.get("AWS_S3_ENDPOINT_URL"),
    ]):
        result["errors"].append("AWS_* env vars not set")
        return result

    try:
        from creative_research.s3_upload import upload_video_to_s3, get_video_meta_from_url, extract_video_id
    except ImportError as e:
        result["errors"].append(f"Cannot import s3_upload: {e}")
        return result

    download_results = job.download_results or []
    scraped = (job.full_result or {}).get("scraped_data", {})
    all_videos = []
    for key in ("youtube_videos", "youtube_shorts", "tiktok_videos", "instagram_videos"):
        all_videos.extend(scraped.get(key, []))

    def find_video_for_url(url: str) -> str | None:
        if not url:
            return None
        vid_id = None
        if "youtube.com" in url or "youtu.be" in url:
            m = re.search(r"(?:v=|shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
            vid_id = m.group(1) if m else None
        elif "tiktok.com" in url:
            m = re.search(r"/video/(\d+)", url)
            vid_id = m.group(1) if m else None
        elif "instagram.com" in url:
            m = re.search(r"instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)", url)
            if not m:
                m = re.search(r"instagram\.com/explore/tags/([a-zA-Z0-9_]+)", url)
            vid_id = m.group(1) if m else None
        if not vid_id:
            return None
        # yt-dlp may save without extension (e.g. vid_xxx/abc123)
        for p in output_dir.rglob("*"):
            if p.is_file() and p.name != ".DS_Store":
                if p.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov"):
                    if vid_id in str(p):
                        return str(p)
                elif vid_id in p.name or vid_id in str(p):
                    # No extension - check if it's a video (yt-dlp often saves MP4 without ext)
                    return str(p)
        return None

    # Build list of (url, video_path) from download_results or scan
    items_to_upload = []
    seen_paths = set()

    for dr in download_results:
        url = dr.get("url", "")
        vpath = dr.get("video_path") or dr.get("videoPath") or dr.get("path")
        if not vpath and url:
            vpath = find_video_for_url(url)
        if vpath and Path(vpath).exists() and vpath not in seen_paths:
            items_to_upload.append((url, vpath))
            seen_paths.add(vpath)

    # If no items from download_results, scan output_dir and match to scraped URLs
    if not items_to_upload:
        for p in output_dir.rglob("*.*"):
            if p.suffix.lower() not in (".mp4", ".webm", ".mkv", ".mov"):
                continue
            if str(p) in seen_paths:
                continue
            # Try to match by video ID in path
            for v in all_videos:
                v_url = v.get("url", "")
                if find_video_for_url(v_url) == str(p):
                    items_to_upload.append((v_url, str(p)))
                    seen_paths.add(str(p))
                    break
        # If still empty, add all found videos (include files without extension - yt-dlp)
        if not items_to_upload:
            for p in output_dir.rglob("*"):
                if not p.is_file() or p.name == ".DS_Store":
                    continue
                if str(p) in seen_paths:
                    continue
                if p.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov"):
                    items_to_upload.append(("", str(p)))
                    seen_paths.add(str(p))
                elif not p.suffix and p.name and not p.name.startswith("."):
                    # No extension - likely video from yt-dlp
                    items_to_upload.append(("", str(p)))
                    seen_paths.add(str(p))

    logger.info("Cache upload: job=%s, items_to_upload=%d", job_id, len(items_to_upload))

    for source_url, video_path in items_to_upload:
        path_obj = Path(video_path)
        if not path_obj.exists():
            result["failed"] += 1
            continue

        meta = get_video_meta_from_url(source_url, all_videos) if source_url else {}
        platform = meta.get("platform", "")
        if not platform and "youtube.com" in source_url:
            platform = "youtube"
        elif not platform and "tiktok.com" in source_url:
            platform = "tiktok"
        elif not platform and "instagram.com" in source_url:
            platform = "instagram"

        s3_path = upload_video_to_s3(
            video_path,
            str(job_id),
            source_url or path_obj.stem,
            platform=platform,
        )
        if not s3_path:
            result["failed"] += 1
            result["errors"].append(f"Upload failed: {path_obj.name}")
            continue

        try:
            vid_id = extract_video_id(source_url) if source_url else path_obj.stem
            PipelineVideo.objects.create(
                job=job,
                s3_path=s3_path,
                source_url=source_url,
                platform=platform,
                video_id=vid_id,
                title=(meta.get("title") or path_obj.stem)[:512],
                duration_sec=meta.get("duration_sec"),
                file_size_bytes=path_obj.stat().st_size,
                transcript=(meta.get("transcript") or "")[:10000],
                views=meta.get("views"),
                likes=meta.get("likes"),
                comments_count=meta.get("comments_count"),
                shares=meta.get("shares"),
                author=(meta.get("author") or "")[:256],
                published_at=(meta.get("published_at") or "")[:64],
                metadata={
                    "gemini_analysis": (meta.get("gemini_analysis") or "")[:5000],
                    "cta_summary": (meta.get("cta_summary") or "")[:500],
                },
            )
            result["uploaded"] += 1
            logger.info("PipelineVideo created from cache: %s", s3_path[:80])
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(str(e)[:200])
            logger.exception("PipelineVideo create failed: %s", e)

    return result


def run_pipeline_for_job_cached(job_id: str) -> None:
    """
    Run pipeline with cache: same as main pipeline but keeps downloads on disk.
    Stores output_dir in job.metadata, runs upload from cache.
    """
    from pipeline_jobs.runner import _serialize_result
    from pipeline_jobs.models import PipelineJob, PipelineStage
    from creative_research.pipeline_v2 import run_pipeline_v2

    try:
        job = PipelineJob.objects.get(pk=job_id)
    except PipelineJob.DoesNotExist:
        return

    job.status = PipelineJob.Status.RUNNING
    job.save(update_fields=["status", "updated_at"])

    for i, name in enumerate(PipelineStage.STAGE_ORDER):
        PipelineStage.objects.get_or_create(
            job=job,
            stage_name=name,
            defaults={"stage_order": i, "status": PipelineStage.StageStatus.PENDING},
        )

    stage_order_map = {name: i for i, name in enumerate(PipelineStage.STAGE_ORDER)}

    def on_stage(stage_name: str):
        now = timezone.now()
        order = stage_order_map.get(stage_name, 0)
        completed_names = [s for s, o in stage_order_map.items() if o < order]
        PipelineStage.objects.filter(job=job, stage_order__lt=order).exclude(
            status=PipelineStage.StageStatus.COMPLETED
        ).update(status=PipelineStage.StageStatus.COMPLETED, completed_at=now)
        PipelineStage.objects.filter(job=job, stage_name=stage_name).update(
            status=PipelineStage.StageStatus.RUNNING, started_at=now
        )
        meta = dict(job.metadata or {})
        meta.setdefault("completed_stages", [])
        meta.setdefault("stage_completed_at", {})
        for prev_name in completed_names:
            if prev_name not in meta["completed_stages"]:
                meta["completed_stages"].append(prev_name)
            meta["stage_completed_at"][prev_name] = now.isoformat()
        meta["current_stage"] = stage_name
        meta["updated_at"] = now.isoformat()
        job.metadata = meta
        job.current_stage = stage_name
        job.save(update_fields=["current_stage", "metadata", "updated_at"])

    output_dir = _project_root / "downloads" / "videos" / str(job_id)
    result = None

    try:
        if job.skip_apify:
            os.environ["SKIP_APIFY"] = "1"
        else:
            os.environ.pop("SKIP_APIFY", None)

        result = run_pipeline_v2(
            job.product_url,
            download_videos=True,
            apify_only=False,
            max_videos_total=20,
            max_videos_to_download=20,  # Download all videos shown in report (align with DB/S3)
            max_videos_to_analyze=5,
            output_dir=str(output_dir),
            on_stage=on_stage,
        )

        serialized = _serialize_result(result)
        report_popular = result.get("report_popular", result.get("report", ""))
        report_all_videos = result.get("report_all_videos", "")

        job.report = report_popular
        job.report_all_videos = report_all_videos
        job.scripts = report_popular if report_popular else ""
        job.keywords = serialized["keywords"]
        job.video_analyses = serialized["video_analyses"]
        job.download_results = serialized["download_results"]
        job.scraped_data_summary = serialized["scraped_data_summary"]
        job.full_result = serialized["full_result"]
        job.status = PipelineJob.Status.COMPLETED
        job.current_stage = None
        job.error_message = None
        meta = dict(job.metadata or {})
        meta["completed_stages"] = list(PipelineStage.STAGE_ORDER)
        meta.setdefault("stage_completed_at", {})
        meta["stage_completed_at"].update(
            {s: timezone.now().isoformat() for s in PipelineStage.STAGE_ORDER if s not in meta["stage_completed_at"]}
        )
        meta["current_stage"] = None
        meta["updated_at"] = timezone.now().isoformat()
        meta["summary"] = {
            "video_counts": serialized.get("scraped_data_summary", {}).get("video_counts", {}),
            "keywords_count": len(serialized.get("keywords", {}).get("search_queries", [])),
        }
        meta["cache_output_dir"] = str(output_dir.absolute())
        job.metadata = meta
        job.completed_at = timezone.now()
        job.save()

        # Upload from cache (files still on disk)
        upload_result = upload_videos_from_cache(job_id)
        logger.info("Cache pipeline upload: %s", upload_result)

        # Mark stages completed
        scraped_summary = serialized.get("scraped_data_summary", {})
        video_counts = scraped_summary.get("video_counts", {})
        keywords = serialized.get("keywords", {})
        download_results = serialized.get("download_results", [])
        video_analyses = serialized.get("video_analyses", [])
        report = result.get("report", "")
        scripts = result.get("scripts", "")
        scraped_data = serialized.get("full_result", {}).get("scraped_data", {})
        stage_metadata_map = {
            "fetch_product": {"product_page_length": len(scraped_data.get("product_page_text", ""))},
            "keywords": {
                "search_queries_count": len(keywords.get("search_queries", [])),
                "subreddits_count": len(keywords.get("subreddits", [])),
            },
            "video_scrape": {"video_counts": video_counts},
            "download": {"total": len(download_results), "success": sum(1 for r in download_results if r.get("success"))},
            "analysis": {"videos_analyzed": len(video_analyses)},
            "report": {"report_length": len(report)},
            "scripts": {"scripts_length": len(scripts)},
        }
        now = timezone.now()
        for stage_name in PipelineStage.STAGE_ORDER:
            PipelineStage.objects.filter(job=job, stage_name=stage_name).update(
                status=PipelineStage.StageStatus.COMPLETED,
                completed_at=now,
                metadata=stage_metadata_map.get(stage_name, {}),
            )

        # Save reports to disk
        try:
            if report_popular:
                (_project_root / "report_popular.md").write_text(report_popular, encoding="utf-8")
            if report_all_videos:
                (_project_root / "report_all_videos.md").write_text(report_all_videos, encoding="utf-8")
            if job.scripts:
                (_project_root / "report_full.md").write_text(job.scripts, encoding="utf-8")
        except OSError:
            pass

        # NO DELETE - cache kept on disk

    except Exception as e:
        job.status = PipelineJob.Status.FAILED
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
        if job.current_stage:
            PipelineStage.objects.filter(job=job, stage_name=job.current_stage).update(
                status=PipelineStage.StageStatus.FAILED,
                error_message=str(e),
                completed_at=timezone.now(),
                metadata={"error": str(e)[:500]},
            )
        logger.exception("Cache pipeline failed: %s", e)
