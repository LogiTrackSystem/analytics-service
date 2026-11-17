"""Integración: pagos de Billing (simulado) -> ETL de ingresos -> consulta por la API del dashboard."""
import asyncio
import uuid

from app.ingresos import sincronizar_ingresos


def test_ingresos_sincronizados_se_consultan_por_la_api(api, db):
    # Arrange: Billing (simulado) devuelve un pago cobrado en octubre
    pago = {"id": str(uuid.uuid4()), "envio_id": str(uuid.uuid4()), "cliente_id": str(uuid.uuid4()),
            "monto_cop": "250000.00", "estado": "confirmado", "confirmado_en": "2026-10-05T15:00:00Z"}

    async def billing(url, params=None, default=None):
        return [pago] if url.endswith("/pagos/") else []

    # Act
    asyncio.run(sincronizar_ingresos(db, "http://billing", billing))
    respuesta = api.get("/dashboard/ingresos/mensual", params={"anio": 2026})
    # Assert
    assert respuesta.status_code == 200
    assert respuesta.json()[0]["periodo"] == "2026-10" and float(respuesta.json()[0]["neto_cop"]) == 250000.0
