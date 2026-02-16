from django.urls import path
from . import views

urlpatterns = [
    path("pipeline/start/", views.start_pipeline),
    path("pipeline/status/<uuid:job_id>/", views.job_status),
]
