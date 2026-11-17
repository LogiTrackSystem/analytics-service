# Analytics Service

Panel de control y analítica de LogiTrack. Combina un consumidor de eventos de RabbitMQ (8 routing keys) con un ETL periódico (APScheduler) que hace polling REST sobre Fleet, Shipment, Routing, Tracking Ingestion, Maintenance, Customs y Billing Service, y sirve un dashboard HTML propio.

## Levantar el servicio

1. Crear la base de datos (ver instrucciones del equipo).
2. `python -m venv venv` y activar el entorno virtual.
3. `pip install -r requirements.txt`
4. Copiar `.env.example` a `.env` y completar credenciales reales.
5. `alembic upgrade head`
6. `uvicorn app.main:app --reload --port 8009`
7. Abrir `http://localhost:8009/` en el navegador para ver el dashboard.

## Endpoints

- `GET /` — dashboard visual.
- `GET /dashboard/resumen`, `/entregas-diarias`, `/utilizacion-flota`, `/costo-por-km`, `/eficiencia-combustible`, `/proyeccion-mantenimiento`, `/actividad-reciente` — datos en JSON.
- `GET /dashboard/ingresos/mensual?anio=`, `/dashboard/ingresos/anual`, `/dashboard/ingresos/pedidos?mes=&estado=&cliente_id=` — ingresos en COP (cobrado, reembolsos, neto) calculados desde los pagos por pedido de Billing en cada ciclo de ETL. Solo administrador por el gateway.
- `POST /etl/ejecutar` — dispara un ciclo de ETL inmediato (útil para pruebas).
- `GET /health`

## Eventos que consume

`shipment.created`, `shipment.delivered`, `shipment.incident`, `shipment.returned`, `route.assigned`, `maintenance.alert`, `customs.held`, `customs.cleared`.

---

<!-- entrega-final -->

## Descripción

ETL periódico y dashboard con indicadores: entregas, utilización de flota, costos, mantenimiento e ingresos.

- **Puerto local:** 8009   ·   **Despliegue activo:** <https://logitrack-analytics.onrender.com> (`/health` y `/metrics` públicos)
- **Imagen Docker:** `<usuario-dockerhub>/logitrack-analytics`   ·   **Repositorio de CI/CD:** `LogiTrackSystem/pipelines`

## Variables de entorno

Copia `.env.example` como `.env` y completa los valores. El `.env` **no se sube** al repositorio.

| Variable | Para qué sirve |
|---|---|
| `DATABASE_URL` | Conexión a la base PostgreSQL del servicio (`postgresql://usuario:clave@host:5432/<base>`). Es un secreto. |
| `RABBITMQ_URL` | URL AMQP del bus de eventos RabbitMQ (CloudAMQP en producción). Es un secreto. |
| `FLEET_SERVICE_URL` | URL base de Fleet Service, sin barra final (en local `http://localhost:<puerto>`). |
| `SHIPMENT_SERVICE_URL` | URL base de Shipment Service, sin barra final (en local `http://localhost:<puerto>`). |
| `ROUTING_SERVICE_URL` | URL base de Routing Service, sin barra final (en local `http://localhost:<puerto>`). |
| `TRACKING_SERVICE_URL` | URL base de Tracking Service, sin barra final (en local `http://localhost:<puerto>`). |
| `MAINTENANCE_SERVICE_URL` | URL base de Maintenance Service, sin barra final (en local `http://localhost:<puerto>`). |
| `CUSTOMS_SERVICE_URL` | URL base de Customs Service, sin barra final (en local `http://localhost:<puerto>`). |
| `BILLING_SERVICE_URL` | URL base de Billing Service, sin barra final (en local `http://localhost:<puerto>`). |
| `ETL_INTERVALO_MINUTOS` | Cada cuántos minutos se ejecuta el ETL (por defecto 5). |
| `INTERNAL_API_KEY` | Clave compartida entre el gateway y los servicios: exige la cabecera `X-Internal-Key` en todas las rutas salvo `/health` y `/metrics`. Vacía = sin restricción (solo local). Es un secreto. |

## Documentación de la API

- **Local** (sin `INTERNAL_API_KEY`): <http://localhost:8009/docs> (Swagger) y `http://localhost:8009/openapi.json`.
- **Producción:** el servicio solo atiende peticiones que llegan por el gateway (con `INTERNAL_API_KEY` activa su `/docs` no es público); la documentación de todas las rutas está en <https://logitrack-gateway.onrender.com/docs>.

## Base de datos

- Migraciones con Alembic (`alembic/`): `alembic upgrade head` (el `Dockerfile` ya lo ejecuta al arrancar).
- `db/esquema.sql`: esquema completo de `analytics_db` generado desde las migraciones.
- Datos de ejemplo: este servicio se alimenta de eventos y llamadas de otros servicios; se generan ejecutando el flujo completo (por ejemplo `_pruebas/casos.py` del proyecto).
- Respaldo y restauración: ver `db/README.md`.

## Pruebas

Con el entorno virtual activo y `pip install -r requirements-dev.txt`:

```
pytest tests/unit                    # 2 pruebas unitarias
pytest tests/integration             # 1 prueba de integración
pytest --cov=app --cov-report=term   # toda la suite con cobertura
```

| Prueba | Qué verifica |
|---|---|
| Unitaria 1 | `ingresos.ingresos_por_mes` |
| Unitaria 2 | `ingresos.sincronizar_ingresos` |
| Integración | sincronización de pagos de Billing → consulta de `/dashboard/ingresos/mensual` |

Archivos: `tests/unit/` y `tests/integration/` (test_ingresos_por_mes.py, test_sincronizar_ingresos.py, test_flujo_ingresos.py). Cobertura de `app/` medida: **≈ 70 %**; en cada push y Pull Request GitHub Actions la recalcula y guarda `coverage.xml` como artefacto (`cobertura-analytics`).

## Métricas y monitoreo

Expone `GET /metrics` (formato Prometheus: `http_requests_total` y `http_request_duration_*`). Prometheus y el dashboard de Grafana están en el repositorio `logitrack-monitoring`.

## CI/CD

- `.github/workflows/pr.yml`: en cada push (rama distinta de `main`) y en cada Pull Request a `main` ejecuta el CI reutilizable (lint, pruebas con cobertura, `docker build` y prueba de arranque).
- `.github/workflows/deploy.yml`: al fusionar en `main`, y solo con las pruebas en verde, publica la imagen en Docker Hub y despliega en Render (con verificación de `/health` y rollback manual).
- Detalle y estrategia de ramas: `CICD.md` en el repositorio `LogiTrackSystem/pipelines`.

