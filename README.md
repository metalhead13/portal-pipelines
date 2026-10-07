# Pipeline Portal basado en django  

Portal de operaciones de datos hecho con Django 5.2 y Django REST Framework. Ofrece una aplicación web con inicio de sesión, catálogo de pipelines, ejecuciones, estados, métricas y API de consulta.

La primera ejecución funciona sin Airflow: un pipeline local procesa un CSV de ventas, valida sus registros y calcula métricas. También hay una integración opcional para iniciar DAG y consultar su estado por la API pública de Airflow 3.

## Requisitos

- Ubuntu con Python 3.10 o posterior, `python3-venv` y `python3-pip`.
- Acceso a paquetes Python para la instalación inicial.
- Docker y Docker Compose solamente si quiere usar PostgreSQL local.
- Airflow 3 solamente para ejecutar DAG desde el portal.

## Arranque rápido en Ubuntu

Desde la carpeta `portal-pipelines`:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

El archivo `.env` es una plantilla de valores. **Las variables de entorno deben cargarse** antes de usar Django. Para la primera prueba basta con:

```bash
export DJANGO_DEBUG=1
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

Abra <http://127.0.0.1:8000/>, ingrese con el superusuario, abra **Calidad y resumen de ventas**, suba `samples/ventas.csv` y pulse **Procesar archivo**. Debería ver 4 registros, 8 unidades y ventas totales de 1.875.000,00 (en la pantalla se muestra `1875000.00`). Puede revisar la ejecución en el panel y la API en `/api/runs/`.

Para volver a entrar después de cerrar la terminal, ejecute `source .venv/bin/activate`, exporte las variables requeridas y use `python manage.py runserver`. Para pruebas locales, puede fijar un valor de `DJANGO_SECRET_KEY` en su gestor de entorno o cargar `.env` con `set -a; source .env; set +a` después de reemplazar el valor de ejemplo.

## API

La API usa la sesión de Django. Al entrar en la aplicación, puede consultar:

| Ruta | Función |
| --- | --- |
| `GET /api/pipelines/` | Lista pipelines activos. |
| `GET /api/runs/` | Lista ejecuciones. |
| `GET /api/runs/<uuid>/` | Detalla una ejecución y sus métricas. |

El inicio de ejecuciones se hace mediante formularios autenticados con protección CSRF. La API incluida es de lectura. Los usuarios con acceso al portal pueden ver todas las ejecuciones: esta primera versión está diseñada para una sola organización.

## PostgreSQL con Docker (opcional)

Puede cambiar SQLite por PostgreSQL local sin modificar código:

```bash
docker compose up -d db
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
export POSTGRES_DB=pipeline_portal
export POSTGRES_USER=portal
export POSTGRES_PASSWORD=local-dev-only
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

SQLite y PostgreSQL son bases distintas: al cambiar de una a otra, migre y cree el usuario nuevamente. La contraseña en `compose.yaml` es **solo para desarrollo local**. Compruebe que el puerto 5432 esté libre o cambie su publicación en Compose.

## Conectar Airflow 3 (opcional)

1. Levante una instancia de Airflow 3 por separado y copie `dags/ventas_demo.py` a su carpeta de DAG. Confirme en la interfaz de Airflow que el DAG `ventas_demo` aparece y está habilitado.
2. Obtenga un JWT de la API pública de Airflow con el mecanismo de autenticación de su instalación. Por ejemplo, con el *simple auth manager*, se solicita en `POST /auth/token` usando sus credenciales. El token necesita permisos para crear y leer ejecuciones de ese DAG.
3. En la terminal que inicia Django, configure:

   ```bash
   export AIRFLOW_BASE_URL=http://127.0.0.1:8080
   export AIRFLOW_TOKEN='pegue-aqui-el-jwt'
   ```

4. En `http://127.0.0.1:8000/admin/`, cree un **Pipeline** con nombre `Ventas en Airflow`, slug `ventas-airflow`, motor `Airflow 3` y DAG ID `ventas_demo`.
5. Vuelva al panel, abra el pipeline, pulse **Ejecutar DAG** y luego **Actualizar estado desde Airflow** en la página de la ejecución.

El conector usa `/api/v2/dags/{dag_id}/dagRuns` de Airflow 3. No instala Airflow ni lo inicia por su cuenta. No extrae automáticamente XCom, logs o métricas del DAG: esos resultados se consultan en Airflow; el portal registra el estado de la ejecución. Si su JWT caduca, genere otro y reinicie el servidor Django con el nuevo `AIRFLOW_TOKEN`.

## Archivos principales

| Ruta | Responsabilidad |
| --- | --- |
| `pipelines/models.py` | Definición de pipelines y ejecuciones. |
| `pipelines/services.py` | Validación CSV, cálculo e integración HTTP con Airflow. |
| `pipelines/views.py` | Vistas del portal y API. |
| `pipelines/admin.py` | Administración de pipelines. |
| `templates/` y `static/` | Interfaz web. |
| `dags/ventas_demo.py` | DAG independiente de ejemplo para Airflow 3. |

## Verificación y límites de esta versión

```bash
python manage.py check
python manage.py test pipelines
python manage.py check --deploy
```

El CSV se procesa durante la petición web, con límites de 5 MB y 10.000 filas. Los datos del archivo **no se conservan**: se registra el nombre, el resultado y el error si lo hay. Para archivos grandes, colas de tareas, reintentos o procesamiento distribuido, traslade la ejecución a Airflow o a trabajadores separados. Antes de publicar el portal en Internet configure HTTPS, `DEBUG=0`, secretos, hosts, archivos estáticos, respaldos y permisos detallados; `check --deploy` indica controles pendientes. El servidor `runserver` es solo para desarrollo.

Documentación: [Django](https://docs.djangoproject.com/en/5.2/), [Django REST Framework](https://www.django-rest-framework.org/), [API de Airflow](https://airflow.apache.org/docs/apache-airflow/stable/stable-rest-api-ref.html) y [autenticación de Airflow](https://airflow.apache.org/docs/apache-airflow/stable/security/api.html).
