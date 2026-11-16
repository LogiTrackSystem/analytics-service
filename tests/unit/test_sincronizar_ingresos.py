"""Unitaria 2: ingresos.sincronizar_ingresos copia los pagos de Billing, o conserva lo anterior si Billing cae."""
import asyncio
import uuid

from app.ingresos import sincronizar_ingresos
from app.models import IngresoPedido

PAGO = {"id": str(uuid.uuid4()), "envio_id": str(uuid.uuid4()), "cliente_id": str(uuid.uuid4()),
        "monto_cop": "250000.00", "estado": "confirmado", "confirmado_en": "2026-10-05T15:00:00Z"}


def test_sincronizar_ingresos_guarda_pagos_y_tolera_billing_caido(db):
    async def billing_ok(url, params=None, default=None):
        return [PAGO] if url.endswith("/pagos/") else []

    async def billing_caido(url, params=None, default=None):
        return default

    asyncio.run(sincronizar_ingresos(db, "http://billing", billing_ok))
    assert db.query(IngresoPedido).one().mes_pago == "2026-10"
    resultado = asyncio.run(sincronizar_ingresos(db, "http://billing", billing_caido))
    assert resultado["actualizado"] is False and db.query(IngresoPedido).count() == 1
