from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import PipelineJob
from .runner import start_pipeline_async
from .serializers import (
    PipelineJobSerializer,
    PipelineJobDetailSerializer,
    StartPipelineSerializer,
)


@api_view(["POST"])
def start_pipeline(request):
    """
    Start the product research pipeline for a given product URL.
    Returns immediately with job ID; pipeline runs in background.
    product_url: optional, defaults to PRODUCT_URL from .env
    skip_apify: when True, skip Apify scrapers
    """
    from creative_research.constants import PRODUCT_URL
    serializer = StartPipelineSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    product_url = (serializer.validated_data.get("product_url") or "").strip()
    if not product_url:
        product_url = (PRODUCT_URL or "").strip()
    if not product_url:
        return Response(
            {"product_url": ["product_url required or set PRODUCT_URL in .env"]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    skip_apify = serializer.validated_data.get("skip_apify", False)
    job, created = start_pipeline_async(product_url, skip_apify=skip_apify)
    return Response(
        PipelineJobSerializer(job).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET"])
def job_status(request, job_id):
    """
    Get the status of a pipeline job.
    Includes current stage, all stages with their status, and full result when completed.
    """
    try:
        job = PipelineJob.objects.get(pk=job_id)
    except PipelineJob.DoesNotExist:
        return Response(
            {"detail": "Job not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Use detail serializer for completed jobs (includes report, scripts)
    if job.status == PipelineJob.Status.COMPLETED:
        serializer = PipelineJobDetailSerializer(job)
    else:
        serializer = PipelineJobSerializer(job)

    return Response(serializer.data)
