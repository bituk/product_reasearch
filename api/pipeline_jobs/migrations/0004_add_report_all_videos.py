# Generated for report_all_videos field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pipeline_jobs", "0003_add_job_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="pipelinejob",
            name="report_all_videos",
            field=models.TextField(blank=True, null=True),
        ),
    ]
