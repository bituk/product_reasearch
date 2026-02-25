# Generated for PipelineVideo model (S3 path + metadata per downloaded video)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pipeline_jobs", "0004_add_report_all_videos"),
    ]

    operations = [
        migrations.CreateModel(
            name="PipelineVideo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("s3_path", models.CharField(db_index=True, max_length=1024)),
                ("source_url", models.URLField(blank=True, max_length=2048)),
                ("platform", models.CharField(blank=True, db_index=True, max_length=32)),
                ("video_id", models.CharField(blank=True, db_index=True, max_length=128)),
                ("title", models.CharField(blank=True, max_length=512)),
                ("duration_sec", models.FloatField(blank=True, null=True)),
                ("file_size_bytes", models.BigIntegerField(blank=True, null=True)),
                ("transcript", models.TextField(blank=True)),
                ("views", models.BigIntegerField(blank=True, null=True)),
                ("likes", models.IntegerField(blank=True, null=True)),
                ("comments_count", models.IntegerField(blank=True, null=True)),
                ("shares", models.IntegerField(blank=True, null=True)),
                ("author", models.CharField(blank=True, max_length=256)),
                ("published_at", models.CharField(blank=True, max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="videos",
                        to="pipeline_jobs.pipelinejob",
                    ),
                ),
            ],
            options={
                "db_table": "pipeline_video",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["job", "platform"], name="pipeline_video_job_platform_idx"),
                    models.Index(fields=["job", "source_url"], name="pipeline_video_job_source_idx"),
                ],
            },
        ),
    ]
