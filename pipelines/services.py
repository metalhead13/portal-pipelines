import csv
import io
import os
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import requests
from django.utils import timezone

from .models import PipelineRun


MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 10000
REQUIRED_COLUMNS = {"fecha", "producto", "cantidad", "precio_unitario"}


class PipelineError(Exception):
    pass


def process_sales_csv(upload):
    if upload.size > MAX_CSV_BYTES:
        raise PipelineError("El CSV supera el límite de 5 MB.")
    try:
        content = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PipelineError("Guarde el CSV en UTF-8.") from exc
    reader = csv.DictReader(io.StringIO(content, newline=""))
    if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
        raise PipelineError("El archivo necesita las columnas: fecha, producto, cantidad, precio_unitario.")
    counts = Counter()
    total = Decimal("0")
    rows = 0
    for line_number, row in enumerate(reader, start=2):
        if rows >= MAX_CSV_ROWS:
            raise PipelineError("El CSV supera el límite de 10.000 registros.")
        try:
            date.fromisoformat(row["fecha"].strip())
            product = row["producto"].strip()
            quantity = int(row["cantidad"].strip())
            price = Decimal(row["precio_unitario"].strip())
            if not product or quantity < 1 or quantity > 1_000_000 or price < 0 or price > 1_000_000_000 or not price.is_finite():
                raise ValueError
        except (AttributeError, TypeError, ValueError, InvalidOperation) as exc:
            raise PipelineError(f"Datos inválidos en la línea {line_number}.") from exc
        counts[product] += quantity
        total += quantity * price
        rows += 1
    if rows == 0:
        raise PipelineError("El CSV no contiene registros.")
    return {
        "registros": rows,
        "unidades": sum(counts.values()),
        "productos": len(counts),
        "total_ventas": str(total.quantize(Decimal("0.01"))),
        "producto_mas_vendido": counts.most_common(1)[0][0],
    }


def execute_local(run, upload):
    run.status = PipelineRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])
    try:
        run.metrics = process_sales_csv(upload)
        run.status = PipelineRun.Status.SUCCESS
    except PipelineError as exc:
        run.error_message = str(exc)
        run.status = PipelineRun.Status.FAILED
    run.finished_at = timezone.now()
    run.save(update_fields=["metrics", "status", "error_message", "finished_at"])
    return run


def airflow_request(method, path, **kwargs):
    base_url = os.getenv("AIRFLOW_BASE_URL", "").rstrip("/")
    token = os.getenv("AIRFLOW_TOKEN", "")
    if not base_url or not token:
        raise PipelineError("Configure AIRFLOW_BASE_URL y AIRFLOW_TOKEN para usar Airflow.")
    try:
        response = requests.request(
            method, f"{base_url}/api/v2/{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10, **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PipelineError("No se pudo consultar Airflow. Revise URL, token, permisos y estado del servicio.") from exc


def trigger_airflow(run):
    dag = quote(run.pipeline.dag_id, safe="")
    try:
        result = airflow_request("POST", f"dags/{dag}/dagRuns", json={"conf": {}})
        run.remote_run_id = result["dag_run_id"]
        run.status = PipelineRun.Status.RUNNING if result.get("state") == "running" else PipelineRun.Status.PENDING
        run.started_at = timezone.now()
        run.save(update_fields=["remote_run_id", "status", "started_at"])
    except (PipelineError, KeyError) as exc:
        run.status = PipelineRun.Status.FAILED
        run.error_message = str(exc) if isinstance(exc, PipelineError) else "Airflow no devolvió un ID de ejecución."
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
    return run


def refresh_airflow(run):
    if not run.remote_run_id or run.status in (PipelineRun.Status.SUCCESS, PipelineRun.Status.FAILED):
        return run
    dag = quote(run.pipeline.dag_id, safe="")
    remote_id = quote(run.remote_run_id, safe="")
    result = airflow_request("GET", f"dags/{dag}/dagRuns/{remote_id}")
    state = result.get("state", "queued")
    if state not in {"queued", "running", "success", "failed"}:
        raise PipelineError(f"Estado de Airflow no reconocido: {state}")
    run.status = PipelineRun.Status.PENDING if state == "queued" else state
    if run.status in (PipelineRun.Status.SUCCESS, PipelineRun.Status.FAILED):
        run.finished_at = timezone.now()
        if run.status == PipelineRun.Status.FAILED:
            run.error_message = "El DAG falló. Consulte las tareas y registros en Airflow."
    run.save(update_fields=["status", "finished_at", "error_message"])
    return run
