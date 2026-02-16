"""
Celery tasks for pipeline jobs.
"""
from celery import shared_task

from .runner import run_pipeline_for_job


@shared_task(bind=True, name="pipeline_jobs.run_pipeline")
def run_pipeline_task(self, job_id: str) -> None:
    """
    Celery task to run the product research pipeline for a job.
    """
    run_pipeline_for_job(job_id)
