"""
Celery tasks for pipeline jobs.
"""
from celery import shared_task

from .runner import run_pipeline_for_job
from .cache_pipeline import run_pipeline_for_job_cached, upload_videos_from_cache


@shared_task(bind=True, name="pipeline_jobs.run_pipeline")
def run_pipeline_task(self, job_id: str) -> None:
    """
    Celery task to run the product research pipeline for a job.
    """
    run_pipeline_for_job(job_id)


@shared_task(bind=True, name="pipeline_jobs.run_pipeline_cached")
def run_pipeline_cached_task(self, job_id: str) -> None:
    """
    Run pipeline with cache: keeps downloads on disk, uploads to S3, saves PipelineVideo.
    """
    run_pipeline_for_job_cached(job_id)


@shared_task(bind=True, name="pipeline_jobs.upload_videos_from_cache")
def upload_videos_from_cache_task(self, job_id: str) -> dict:
    """
    Upload cached videos to S3 and create PipelineVideo records for a job.
    Returns {uploaded, failed, errors}.
    """
    return upload_videos_from_cache(job_id)
