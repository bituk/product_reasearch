from django.contrib import admin
from .models import PipelineJob, PipelineStage, PipelineVideo


class PipelineStageInline(admin.TabularInline):
    model = PipelineStage
    extra = 0
    readonly_fields = ["stage_name", "stage_order", "status", "started_at", "completed_at", "error_message"]


class PipelineVideoInline(admin.TabularInline):
    model = PipelineVideo
    extra = 0
    readonly_fields = ["created_at"]
    fields = ["s3_path", "source_url", "platform", "video_id", "title", "duration_sec", "views", "likes"]


@admin.register(PipelineJob)
class PipelineJobAdmin(admin.ModelAdmin):
    list_display = ["id", "product_url_short", "status", "current_stage", "created_at"]
    list_filter = ["status"]
    search_fields = ["product_url"]
    readonly_fields = ["id", "created_at", "updated_at", "completed_at"]
    inlines = [PipelineStageInline, PipelineVideoInline]

    def product_url_short(self, obj):
        return (obj.product_url or "")[:60] + "..." if len(obj.product_url or "") > 60 else obj.product_url

    product_url_short.short_description = "Product URL"
