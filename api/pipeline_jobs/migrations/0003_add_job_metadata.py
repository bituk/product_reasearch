# Generated manually for add_job_metadata

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pipeline_jobs", "0002_add_skip_apify"),
    ]

    operations = [
        migrations.AddField(
            model_name="pipelinejob",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
