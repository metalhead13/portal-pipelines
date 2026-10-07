import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class Pipeline(models.Model):
    class Engine(models.TextChoices):
        CSV = "csv", "CSV local"
        AIRFLOW = "airflow", "Airflow 3"

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    engine = models.CharField(max_length=12, choices=Engine.choices, default=Engine.CSV)
    dag_id = models.CharField(
        max_length=150, blank=True,
        validators=[RegexValidator(r"^[a-zA-Z0-9_.-]+$", "ID de DAG inválido")],
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.engine == self.Engine.AIRFLOW and not self.dag_id:
            raise ValidationError({"dag_id": "Indique el ID del DAG para Airflow."})

    def __str__(self):
        return self.name


class PipelineRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        RUNNING = "running", "En ejecución"
        SUCCESS = "success", "Exitosa"
        FAILED = "failed", "Fallida"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.PROTECT, related_name="runs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    original_filename = models.CharField(max_length=255, blank=True)
    remote_run_id = models.CharField(max_length=250, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.pipeline.slug}: {self.status} ({self.id})"
