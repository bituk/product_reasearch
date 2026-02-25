from django.urls import path
from . import views

urlpatterns = [
    path("pipeline/start/", views.start_pipeline),
    path("pipeline/start-cached/", views.start_pipeline_cached),
    path("pipeline/status/<uuid:job_id>/", views.job_status),
    path("pipeline/<uuid:job_id>/upload-videos/", views.upload_job_videos),
]
