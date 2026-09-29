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
- `POST /etl/ejecutar` — dispara un ciclo de ETL inmediato (útil para pruebas).
- `GET /health`

## Eventos que consume

`shipment.created`, `shipment.delivered`, `shipment.incident`, `shipment.returned`, `route.assigned`, `maintenance.alert`, `customs.held`, `customs.cleared`.