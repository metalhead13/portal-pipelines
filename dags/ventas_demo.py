from datetime import datetime
from decimal import Decimal

from airflow.sdk import dag, task


@dag(dag_id="ventas_demo", start_date=datetime(2026, 1, 1), schedule=None, catchup=False, tags=["portal"])
def ventas_demo():
    @task
    def calcular_resumen():
        ventas = [
            {"producto": "Teclado", "cantidad": 2, "precio": "80000.00"},
            {"producto": "Mouse", "cantidad": 3, "precio": "45000.00"},
        ]
        total = sum((Decimal(item["precio"]) * item["cantidad"] for item in ventas), Decimal("0"))
        resultado = {"registros": len(ventas), "total_ventas": str(total)}
        print(resultado)
        return resultado

    calcular_resumen()


ventas_demo()
