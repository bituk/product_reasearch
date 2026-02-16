from rest_framework import serializers
from .models import PipelineJob, PipelineStage


class PipelineStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineStage
        fields = [
            "stage_name",
            "stage_order",
            "status",
            "error_message",
            "started_at",
            "completed_at",
            "metadata",
        ]


class PipelineJobSerializer(serializers.ModelSerializer):
    stages = PipelineStageSerializer(many=True, read_only=True)

    class Meta:
        model = PipelineJob
        fields = [
            "id",
            "product_url",
            "status",
            "current_stage",
            "error_message",
            "created_at",
            "updated_at",
            "completed_at",
            "metadata",
            "stages",
        ]


class PipelineJobDetailSerializer(serializers.ModelSerializer):
    """Full job details including report, scripts, and structured data."""
    stages = PipelineStageSerializer(many=True, read_only=True)

    class Meta:
        model = PipelineJob
        fields = [
            "id",
            "product_url",
            "status",
            "current_stage",
            "error_message",
            "created_at",
            "updated_at",
            "completed_at",
            "metadata",
            "report",
            "scripts",
            "keywords",
            "video_analyses",
            "download_results",
            "scraped_data_summary",
            "stages",
        ]


class StartPipelineSerializer(serializers.Serializer):
    product_url = serializers.URLField(required=False, allow_blank=True, max_length=2048)
    skip_apify = serializers.BooleanField(required=False, default=False)
