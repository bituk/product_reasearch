from rest_framework import serializers
from .models import PipelineJob, PipelineStage, PipelineVideo


class PipelineVideoSerializer(serializers.ModelSerializer):
    """Video details including presigned URL for S3 download."""

    presigned_url = serializers.SerializerMethodField()

    class Meta:
        model = PipelineVideo
        fields = [
            "id",
            "s3_path",
            "source_url",
            "platform",
            "video_id",
            "title",
            "duration_sec",
            "file_size_bytes",
            "transcript",
            "views",
            "likes",
            "comments_count",
            "shares",
            "author",
            "published_at",
            "metadata",
            "created_at",
            "presigned_url",
        ]

    def get_presigned_url(self, obj):
        from creative_research.s3_upload import generate_presigned_url

        return generate_presigned_url(obj.s3_path) if obj.s3_path else None


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
    videos = PipelineVideoSerializer(many=True, read_only=True)

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
            "videos",
        ]


class PipelineJobDetailSerializer(serializers.ModelSerializer):
    """Full job details including report, scripts, videos with presigned URLs, and structured data."""
    stages = PipelineStageSerializer(many=True, read_only=True)
    videos = PipelineVideoSerializer(many=True, read_only=True)
    report_popular = serializers.CharField(source="report", read_only=True)

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
            "report_popular",
            "report_all_videos",
            "scripts",
            "keywords",
            "video_analyses",
            "download_results",
            "scraped_data_summary",
            "stages",
            "videos",
        ]


class StartPipelineSerializer(serializers.Serializer):
    product_url = serializers.URLField(required=False, allow_blank=True, max_length=2048)
    skip_apify = serializers.BooleanField(required=False, default=False)
