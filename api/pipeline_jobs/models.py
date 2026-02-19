"""
PostgreSQL schema for pipeline job tracking and result storage.
"""
import uuid
from django.db import models


class PipelineJob(models.Model):
    """
    Main job record for a product research pipeline run.
    Tracks status, current stage, and stores the full result.
    """
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_url = models.URLField(max_length=2048, db_index=True)
    skip_apify = models.BooleanField(default=False)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    current_stage = models.CharField(max_length=64, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    # Output: report and scripts (primary deliverables)
    report = models.TextField(blank=True, null=True)  # report_popular (most popular videos)
    report_all_videos = models.TextField(blank=True, null=True)  # report with all videos (max 25)
    scripts = models.TextField(blank=True, null=True)

    # Structured data (JSONB for flexible querying)
    keywords = models.JSONField(default=dict, blank=True)  # search_queries, subreddits
    video_analyses = models.JSONField(default=list, blank=True)
    download_results = models.JSONField(default=list, blank=True)
    scraped_data_summary = models.JSONField(default=dict, blank=True)  # condensed videos, comments
    full_result = models.JSONField(default=dict, blank=True)  # complete result for audit
    metadata = models.JSONField(default=dict, blank=True)  # progress updated as each stage completes

    class Meta:
        db_table = "pipeline_job"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"PipelineJob({self.product_url[:50]}..., {self.status})"


class PipelineStage(models.Model):
    """
    Granular stage tracking for each pipeline step.
    """
    class StageStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    STAGE_ORDER = [
        "fetch_product",
        "keywords",
        "video_scrape",
        "download",
        "analysis",
        "report",
        "scripts",
    ]

    job = models.ForeignKey(
        PipelineJob,
        on_delete=models.CASCADE,
        related_name="stages",
    )
    stage_name = models.CharField(max_length=64, db_index=True)
    stage_order = models.PositiveSmallIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=StageStatus.choices,
        default=StageStatus.PENDING,
    )
    error_message = models.TextField(blank=True, null=True)

    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    # Optional: store stage-specific output (e.g. video count for scrape)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "pipeline_stage"
        ordering = ["stage_order"]
        unique_together = [("job", "stage_name")]

    def __str__(self):
        return f"Stage({self.job_id}, {self.stage_name}, {self.status})"
