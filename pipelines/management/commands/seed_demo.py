from django.core.management.base import BaseCommand

from pipelines.models import Pipeline


class Command(BaseCommand):
    help = "Crea el pipeline CSV de demostración sin duplicarlo"

    def handle(self, *args, **options):
        pipeline, created = Pipeline.objects.get_or_create(
            slug="ventas-csv",
            defaults={
                "name": "Calidad y resumen de ventas",
                "description": "Valida fechas, productos, cantidades y precios; calcula ventas y unidades.",
                "engine": Pipeline.Engine.CSV,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"{'Creado' if created else 'Ya existe'}: {pipeline.name}"))
