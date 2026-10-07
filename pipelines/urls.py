from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("pipelines/<slug:slug>/", views.pipeline_detail, name="pipeline_detail"),
    path("pipelines/<slug:slug>/start/", views.start_run, name="start_run"),
    path("runs/<uuid:run_id>/", views.run_detail, name="run_detail"),
    path("runs/<uuid:run_id>/sync/", views.sync_run, name="sync_run"),
    path("api/pipelines/", views.PipelineListAPI.as_view(), name="api_pipelines"),
    path("api/runs/", views.RunListAPI.as_view(), name="api_runs"),
    path("api/runs/<uuid:pk>/", views.RunDetailAPI.as_view(), name="api_run_detail"),
]
