import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from .models import Pipeline, PipelineRun
from .services import refresh_airflow


class PortalFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("analista", password="test-password-123")
        cls.pipeline = Pipeline.objects.create(name="Ventas", slug="ventas", engine=Pipeline.Engine.CSV)

    def test_login_required_for_dashboard_and_api(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
        self.assertEqual(self.client.get(reverse("api_runs")).status_code, 403)

    def test_csv_upload_creates_a_successful_run_and_metrics(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("dashboard")), "Ventas")
        self.assertContains(self.client.get(reverse("pipeline_detail", args=["ventas"])), "Iniciar pipeline")
        data = b"fecha,producto,cantidad,precio_unitario\n2026-10-01,Teclado,2,80000\n2026-10-02,Mouse,1,45000\n"
        upload = SimpleUploadedFile("ventas.csv", data, content_type="text/csv")
        response = self.client.post(reverse("start_run", args=["ventas"]), {"file": upload})
        self.assertEqual(response.status_code, 302)
        run = PipelineRun.objects.get()
        self.assertEqual(run.status, PipelineRun.Status.SUCCESS)
        self.assertEqual(run.metrics["total_ventas"], "205000.00")
        self.assertEqual(run.metrics["producto_mas_vendido"], "Teclado")
        self.assertContains(self.client.get(response.url), "205000.00")
        self.assertEqual(self.client.get(reverse("api_run_detail", args=[run.id])).json()["status"], "success")

    def test_invalid_row_is_tracked_as_failed(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile("mal.csv", b"fecha,producto,cantidad,precio_unitario\n2026-10-01,Teclado,0,10\n")
        self.client.post(reverse("start_run", args=["ventas"]), {"file": upload})
        run = PipelineRun.objects.get()
        self.assertEqual(run.status, PipelineRun.Status.FAILED)
        self.assertIn("línea 2", run.error_message)

    def test_post_action_requires_csrf(self):
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.user)
        self.assertEqual(strict_client.post(reverse("start_run", args=["ventas"])).status_code, 403)

    def test_airflow_trigger_and_refresh(self):
        airflow = Pipeline.objects.create(name="Airflow", slug="airflow", engine=Pipeline.Engine.AIRFLOW, dag_id="demo_dag")
        self.client.force_login(self.user)
        with patch.dict(os.environ, {"AIRFLOW_BASE_URL": "http://airflow:8080", "AIRFLOW_TOKEN": "example-token"}):
            with patch("pipelines.services.requests.request") as request:
                request.return_value.json.return_value = {"dag_run_id": "manual__2026-10-07", "state": "queued"}
                self.client.post(reverse("start_run", args=[airflow.slug]))
                run = PipelineRun.objects.get()
                self.assertEqual(run.remote_run_id, "manual__2026-10-07")
                self.assertEqual(run.status, PipelineRun.Status.PENDING)
                self.assertIn("/api/v2/dags/demo_dag/dagRuns", request.call_args.args[1])
                request.return_value.json.return_value = {"state": "success"}
                refresh_airflow(run)
                self.assertEqual(run.status, PipelineRun.Status.SUCCESS)

    def test_airflow_missing_config_marks_run_failed(self):
        airflow = Pipeline.objects.create(name="Airflow", slug="airflow", engine=Pipeline.Engine.AIRFLOW, dag_id="demo_dag")
        self.client.force_login(self.user)
        with patch.dict(os.environ, {"AIRFLOW_BASE_URL": "", "AIRFLOW_TOKEN": ""}):
            self.client.post(reverse("start_run", args=[airflow.slug]))
        self.assertEqual(PipelineRun.objects.get().status, PipelineRun.Status.FAILED)
