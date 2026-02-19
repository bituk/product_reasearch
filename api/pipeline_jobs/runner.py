"""
Background pipeline runner with stage tracking and DB persistence.
Uses Celery when available (Redis broker), otherwise falls back to threading.
"""
import json
import shutil
import threading
from dataclasses import asdict
from pathlib import Path

from django.utils import timezone


def _delete_job_downloads(output_dir: Path) -> None:
    """
    Recursively delete the job's download directory (videos, transcripts, subdirs).
    Videos are stored in output_dir/vid_xxx/video.mp4, so we need rmtree.
    """
    if not output_dir.exists():
        return
    try:
        shutil.rmtree(output_dir)
    except OSError:
        pass

# Add project root to path for creative_research imports
import sys
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def _serialize_scraped_data(scraped) -> dict:
    """Convert ScrapedData dataclass to JSON-serializable dict."""
    if scraped is None:
        return {}

    def _video_to_dict(v):
        d = asdict(v)
        # Remove raw if it has non-serializable content
        if "raw" in d and d["raw"]:
            try:
                json.dumps(d["raw"])
            except (TypeError, ValueError):
                d["raw"] = {}
        return d

    def _comment_to_dict(c):
        d = asdict(c)
        if "raw" in d and d["raw"]:
            try:
                json.dumps(d["raw"])
            except (TypeError, ValueError):
                d["raw"] = {}
        return d

    return {
        "product_url": getattr(scraped, "product_url", ""),
        "product_page_text": (getattr(scraped, "product_page_text", "") or "")[:5000],
        "youtube_videos": [_video_to_dict(v) for v in getattr(scraped, "youtube_videos", [])],
        "youtube_shorts": [_video_to_dict(v) for v in getattr(scraped, "youtube_shorts", [])],
        "tiktok_videos": [_video_to_dict(v) for v in getattr(scraped, "tiktok_videos", [])],
        "instagram_videos": [_video_to_dict(v) for v in getattr(scraped, "instagram_videos", [])],
        "youtube_comments": [_comment_to_dict(c) for c in getattr(scraped, "youtube_comments", [])],
        "reddit_posts_and_comments": [
            _comment_to_dict(c) for c in getattr(scraped, "reddit_posts_and_comments", [])
        ],
        "amazon_reviews_text": (getattr(scraped, "amazon_reviews_text", "") or "")[:3000],
        "competitor_research": (getattr(scraped, "competitor_research", "") or "")[:5000],
    }


def _serialize_result(result: dict) -> dict:
    """Prepare pipeline result for DB storage (JSON-serializable)."""
    scraped = result.get("scraped_data")
    scraped_summary = _serialize_scraped_data(scraped) if scraped else {}

    # Condensed summary for scraped_data_summary (fewer videos to save space)
    summary = {}
    if scraped_summary:
        summary = {
            "video_counts": {
                "youtube": len(scraped_summary.get("youtube_videos", [])),
                "youtube_shorts": len(scraped_summary.get("youtube_shorts", [])),
                "tiktok": len(scraped_summary.get("tiktok_videos", [])),
                "instagram": len(scraped_summary.get("instagram_videos", [])),
            },
            "comment_counts": {
                "youtube": len(scraped_summary.get("youtube_comments", [])),
                "reddit": len(scraped_summary.get("reddit_posts_and_comments", [])),
            },
        }

    full_result = {
        "product_link": result.get("product_link"),
        "keywords": result.get("keywords", {}),
        "download_results": result.get("download_results", []),
        "video_analyses": result.get("video_analyses", []),
        "scraped_data": scraped_summary,
    }

    return {
        "keywords": result.get("keywords", {}),
        "video_analyses": result.get("video_analyses", []),
        "download_results": result.get("download_results", []),
        "scraped_data_summary": summary,
        "full_result": full_result,
    }


def run_pipeline_for_job(job_id: str) -> None:
    """
    Run the pipeline for a given job (called from background thread).
    Updates PipelineJob and PipelineStage as it progresses.
    """
    from pipeline_jobs.models import PipelineJob, PipelineStage

    try:
        job = PipelineJob.objects.get(pk=job_id)
    except PipelineJob.DoesNotExist:
        return

    job.status = PipelineJob.Status.RUNNING
    job.save(update_fields=["status", "updated_at"])

    # Create stage records
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
        # Mark all previous stages as completed
        PipelineStage.objects.filter(
            job=job, stage_order__lt=order
        ).exclude(status=PipelineStage.StageStatus.COMPLETED).update(
            status=PipelineStage.StageStatus.COMPLETED,
            completed_at=now,
        )
        # Update current stage to running
        PipelineStage.objects.filter(job=job, stage_name=stage_name).update(
            status=PipelineStage.StageStatus.RUNNING,
            started_at=now,
        )
        # Update job metadata immediately (returned by GET API)
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

    import os
    from creative_research.pipeline_v2 import run_pipeline_v2

    # Job-specific output dir so we can delete it on success or failure
    output_dir = _project_root / "downloads" / "videos" / str(job_id)
    result = None

    try:
        # Set SKIP_APIFY for this run if requested
        if job.skip_apify:
            os.environ["SKIP_APIFY"] = "1"
        else:
            os.environ.pop("SKIP_APIFY", None)

        result = run_pipeline_v2(
            job.product_url,
            download_videos=True,
            apify_only=False,  # Use all four scrapers: YouTube, Shorts, TikTok, Instagram
            max_videos_total=20,
            max_videos_to_download=5,
            max_videos_to_analyze=5,
            output_dir=str(output_dir),
            on_stage=on_stage,
        )

        serialized = _serialize_result(result)

        report_popular = result.get("report_popular", result.get("report", ""))
        report_all_videos = result.get("report_all_videos", "")
        scripts_only = result.get("scripts", "")
        job.report = report_popular
        job.report_all_videos = report_all_videos
        # scripts field stores full report + generated scripts (complete deliverable)
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
        job.metadata = meta
        job.completed_at = timezone.now()
        job.save()

        # Mark all stages completed and populate stage metadata
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
            "download": {
                "total": len(download_results),
                "success": sum(1 for r in download_results if r.get("success")),
            },
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
            # Backward compat: report_full.md = popular variant
            if job.scripts:
                (_project_root / "report_full.md").write_text(job.scripts, encoding="utf-8")
        except OSError:
            pass

    except Exception as e:
        job.status = PipelineJob.Status.FAILED
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])

        # Mark current stage as failed with error in metadata
        if job.current_stage:
            PipelineStage.objects.filter(job=job, stage_name=job.current_stage).update(
                status=PipelineStage.StageStatus.FAILED,
                error_message=str(e),
                completed_at=timezone.now(),
                metadata={"error": str(e)[:500]},
            )
    finally:
        # Delete downloaded videos after job finishes (success or failure)
        _delete_job_downloads(output_dir)


def start_pipeline_async(product_url: str, *, skip_apify: bool = False) -> tuple["PipelineJob", bool]:
    """
    Create a PipelineJob and start the pipeline via Celery (or threading fallback).
    Returns (job, created) - created is False if existing job was returned.
    Skips starting if a job with same product_url is already PENDING, RUNNING, or COMPLETED.
    skip_apify: when True, skip Apify scrapers
    """
    from pipeline_jobs.models import PipelineJob

    existing = PipelineJob.objects.filter(
        product_url=product_url,
        status__in=[
            PipelineJob.Status.PENDING,
            PipelineJob.Status.RUNNING,
            PipelineJob.Status.COMPLETED,
        ],
    ).order_by("-created_at").first()

    if existing:
        return existing, False

    job = PipelineJob.objects.create(
        product_url=product_url,
        skip_apify=skip_apify,
        status=PipelineJob.Status.PENDING,
    )

    # Prefer Celery when available (requires Redis)
    try:
        from pipeline_jobs.tasks import run_pipeline_task
        run_pipeline_task.delay(str(job.id))
    except Exception:
        # Fallback to threading when Celery/Redis unavailable
        thread = threading.Thread(target=run_pipeline_for_job, args=(str(job.id),))
        thread.daemon = True
        thread.start()

    return job, True
