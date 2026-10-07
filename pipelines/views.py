from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework import generics, serializers

from .models import Pipeline, PipelineRun
from .services import MAX_CSV_BYTES, PipelineError, execute_local, refresh_airflow, trigger_airflow


@login_required
def dashboard(request):
    pipelines = Pipeline.objects.filter(active=True).annotate(run_count=Count("runs")).order_by("name")
    recent = PipelineRun.objects.select_related("pipeline", "requested_by")[:10]
    return render(request, "pipelines/dashboard.html", {
        "pipelines": pipelines, "recent": recent,
        "total_pipelines": pipelines.count(),
        "total_runs": PipelineRun.objects.count(),
        "successful_runs": PipelineRun.objects.filter(status=PipelineRun.Status.SUCCESS).count(),
    })


@login_required
def pipeline_detail(request, slug):
    pipeline = get_object_or_404(Pipeline, slug=slug, active=True)
    return render(request, "pipelines/pipeline_detail.html", {
        "pipeline": pipeline,
        "runs": pipeline.runs.select_related("requested_by")[:30],
    })


@login_required
@require_POST
def start_run(request, slug):
    pipeline = get_object_or_404(Pipeline, slug=slug, active=True)
    upload = request.FILES.get("file")
    if pipeline.engine == Pipeline.Engine.CSV:
        if not upload or not upload.name.lower().endswith(".csv"):
            messages.error(request, "Seleccione un archivo .csv.")
            return redirect("pipeline_detail", slug=slug)
        if upload.size > MAX_CSV_BYTES:
            messages.error(request, "El CSV supera el límite de 5 MB.")
            return redirect("pipeline_detail", slug=slug)
    run = PipelineRun.objects.create(
        pipeline=pipeline, requested_by=request.user,
        original_filename=upload.name[:255] if upload and pipeline.engine == Pipeline.Engine.CSV else "",
    )
    if pipeline.engine == Pipeline.Engine.CSV:
        execute_local(run, upload)
    else:
        trigger_airflow(run)
    return redirect("run_detail", run_id=run.id)


@login_required
def run_detail(request, run_id):
    run = get_object_or_404(PipelineRun.objects.select_related("pipeline", "requested_by"), pk=run_id)
    return render(request, "pipelines/run_detail.html", {"run": run})


@login_required
@require_POST
def sync_run(request, run_id):
    run = get_object_or_404(PipelineRun.objects.select_related("pipeline"), pk=run_id)
    if run.pipeline.engine != Pipeline.Engine.AIRFLOW:
        raise Http404
    try:
        refresh_airflow(run)
    except PipelineError as exc:
        messages.error(request, str(exc))
    return redirect("run_detail", run_id=run.id)


class PipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pipeline
        fields = ("id", "name", "slug", "description", "engine", "active")


class RunSerializer(serializers.ModelSerializer):
    pipeline = serializers.CharField(source="pipeline.slug")
    requested_by = serializers.CharField(source="requested_by.username")

    class Meta:
        model = PipelineRun
        fields = ("id", "pipeline", "requested_by", "status", "original_filename",
                  "remote_run_id", "metrics", "error_message", "created_at", "started_at", "finished_at")


class PipelineListAPI(generics.ListAPIView):
    queryset = Pipeline.objects.filter(active=True).order_by("name")
    serializer_class = PipelineSerializer


class RunListAPI(generics.ListAPIView):
    queryset = PipelineRun.objects.select_related("pipeline", "requested_by").all()
    serializer_class = RunSerializer


class RunDetailAPI(generics.RetrieveAPIView):
    queryset = PipelineRun.objects.select_related("pipeline", "requested_by").all()
    serializer_class = RunSerializer
