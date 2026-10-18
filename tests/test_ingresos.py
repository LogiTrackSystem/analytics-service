"""Ingresos por pedido, mes y año: ETL desde Billing, agregados y endpoints."""
import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app import etl
from app.ingresos import (
    PAGINA, ingresos_por_anio, ingresos_por_mes, mes_colombia, neto_del_periodo, sincronizar_ingresos,
)
from app.models import IngresoPedido, ResumenEjecutivo

BILLING = "http://billing"


def pago(monto, estado="confirmado", confirmado="2026-10-05T15:00:00Z", reembolsado=None, codigo=None, cliente=None):
    return {
        "id": str(uuid.uuid4()), "envio_id": str(uuid.uuid4()), "codigo_envio": codigo,
        "cliente_id": cliente or str(uuid.uuid4()), "monto_cop": str(monto), "moneda": "COP",
        "estado": estado, "metodo": "simulado", "referencia": None, "creado_en": confirmado,
        "confirmado_en": None if estado == "pendiente" else confirmado, "reembolsado_en": reembolsado,
    }


def factura(p, numero):
    return {"id": str(uuid.uuid4()), "numero": numero, "pago_id": p["id"], "envio_id": p["envio_id"],
            "estado": "anulada" if p["estado"] == "reembolsado" else "emitida"}


def billing_falso(pagos, facturas=None, caido=False, pagina=PAGINA):
    """get_json falso que imita la paginación limite/offset de Billing."""
    facturas = facturas or []

    async def get_json(url, params=None, default=None):
        if caido or not (url.endswith("/pagos/") or url.endswith("/facturas-pedido/")):
            return default
        datos = pagos if url.endswith("/pagos/") else facturas
        off, lim = params["offset"], params["limite"]
        return datos[off:off + lim]
    return get_json


def sincronizar(db, pagos, facturas=None, **kw):
    return asyncio.run(sincronizar_ingresos(db, BILLING, billing_falso(pagos, facturas, **kw)))


def test_mes_se_calcula_en_hora_de_colombia():
    # 2026-11-01 02:00 UTC = 2026-10-31 21:00 en Colombia -> sigue siendo octubre
    assert mes_colombia(datetime(2026, 11, 1, 2, 0, tzinfo=timezone.utc)) == "2026-10"
    assert mes_colombia(datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc)) == "2026-11"
    assert mes_colombia(None) is None


def test_sincroniza_pagos_con_su_factura(db):
    p = pago("250000.00", codigo="ENV-00000001")
    r = sincronizar(db, [p], [factura(p, "FP-00000001")])
    assert r == {"actualizado": True, "pagos": 1}
    fila = db.query(IngresoPedido).one()
    assert fila.codigo_envio == "ENV-00000001"
    assert fila.factura_numero == "FP-00000001" and fila.factura_estado == "emitida"
    assert fila.monto_cop == Decimal("250000.00") and fila.mes_pago == "2026-10"


def test_pago_pendiente_no_cuenta_como_ingreso(db):
    sincronizar(db, [pago(100000, "pendiente"), pago(200000)])
    meses = ingresos_por_mes(db)
    assert len(meses) == 1
    assert meses[0]["pedidos_cobrados"] == 1 and meses[0]["bruto_cop"] == Decimal("200000")


def test_mensual_bruto_reembolso_neto_y_ticket(db):
    sincronizar(db, [
        pago(300000, confirmado="2026-09-10T15:00:00Z"),
        pago(100000, confirmado="2026-10-02T15:00:00Z"),
        pago(200000, confirmado="2026-10-03T15:00:00Z"),
        # cobrado en septiembre, reembolsado en octubre: el reembolso resta en octubre
        pago(50000, "reembolsado", confirmado="2026-09-20T15:00:00Z", reembolsado="2026-10-04T15:00:00Z"),
    ])
    sep, octu = ingresos_por_mes(db)
    assert sep["periodo"] == "2026-09"
    assert sep["pedidos_cobrados"] == 2 and sep["bruto_cop"] == Decimal("350000") and sep["neto_cop"] == Decimal("350000")
    assert octu["periodo"] == "2026-10"
    assert octu["pedidos_cobrados"] == 2 and octu["bruto_cop"] == Decimal("300000")
    assert octu["pedidos_reembolsados"] == 1 and octu["reembolsos_cop"] == Decimal("50000")
    assert octu["neto_cop"] == Decimal("250000")
    assert octu["ticket_promedio_cop"] == Decimal("150000.00")


def test_anual_suma_los_meses_y_filtra_por_anio(db):
    sincronizar(db, [
        pago(100000, confirmado="2025-12-31T20:00:00Z"),
        pago(200000, confirmado="2026-01-15T15:00:00Z"),
        pago(300000, confirmado="2026-10-05T15:00:00Z"),
    ])
    anios = ingresos_por_anio(db)
    assert [a["periodo"] for a in anios] == ["2025", "2026"]
    assert anios[1]["bruto_cop"] == Decimal("500000") and anios[1]["pedidos_cobrados"] == 2
    assert [m["periodo"] for m in ingresos_por_mes(db, 2026)] == ["2026-01", "2026-10"]


def test_sin_datos_devuelve_listas_vacias_y_cero(db):
    assert ingresos_por_mes(db) == [] and ingresos_por_anio(db) == []
    assert neto_del_periodo(db) == (Decimal("0.00"), Decimal("0.00"))


def test_billing_caido_conserva_la_ultima_version(db):
    sincronizar(db, [pago(100000)])
    r = sincronizar(db, [], caido=True)
    assert r["actualizado"] is False
    assert db.query(IngresoPedido).count() == 1


def test_resincronizar_no_duplica_y_refleja_el_reembolso(db):
    p = pago(100000)
    sincronizar(db, [p])
    p2 = dict(p, estado="reembolsado", reembolsado_en="2026-10-06T15:00:00Z")
    sincronizar(db, [p2])
    fila = db.query(IngresoPedido).one()
    assert fila.estado_pago == "reembolsado" and fila.mes_reembolso == "2026-10"
    assert ingresos_por_mes(db)[0]["neto_cop"] == Decimal("0")


def test_pago_con_monto_invalido_se_ignora_sin_romper_el_resto(db):
    malo = pago(1)
    malo["monto_cop"] = "abc"
    r = sincronizar(db, [malo, pago(200000)])
    assert r["pagos"] == 1


def test_paginacion_recorre_todas_las_paginas(db):
    pagos = [pago(1000) for _ in range(PAGINA + 20)]
    r = sincronizar(db, pagos)
    assert r["pagos"] == PAGINA + 20
    assert ingresos_por_mes(db)[0]["pedidos_cobrados"] == PAGINA + 20


def test_neto_del_periodo_usa_mes_y_anio_en_curso(db):
    sincronizar(db, [
        pago(100000, confirmado="2026-10-05T15:00:00Z"),
        pago(400000, confirmado="2026-03-05T15:00:00Z"),
        pago(900000, confirmado="2025-10-05T15:00:00Z"),
    ])
    ahora = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
    assert neto_del_periodo(db, ahora) == (Decimal("100000"), Decimal("500000"))


def test_etl_completo_actualiza_el_resumen_ejecutivo(db, monkeypatch):
    """El ciclo completo del ETL (con los demás servicios 'sin datos') deja los ingresos en el resumen."""
    p = pago(120000, confirmado=datetime.now(timezone.utc).isoformat())
    base = billing_falso([p], [factura(p, "FP-00000007")])

    async def get_json(url, params=None, default=None):
        if url.startswith(BILLING):
            return await base(url, params, default)
        return default if default is not None else []

    monkeypatch.setattr(etl, "_get_json", get_json)
    monkeypatch.setattr(etl, "BILLING_SERVICE_URL", BILLING)
    monkeypatch.setattr(etl, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    resultado = asyncio.run(etl.ejecutar_ciclo_etl())
    assert resultado["ok"], resultado
    assert resultado["detalles"]["ingresos"]["pagos"] == 1
    resumen = db.query(ResumenEjecutivo).one()
    assert resumen.ingresos_mes_actual_cop == Decimal("120000")
    assert resumen.ingresos_anio_actual_cop == Decimal("120000")


# ---------------- endpoints ----------------

def test_endpoint_mensual_y_anual(api, db):
    sincronizar(db, [pago(100000, confirmado="2026-10-05T15:00:00Z"), pago(50000, confirmado="2026-09-05T15:00:00Z")])
    mensual = api.get("/dashboard/ingresos/mensual").json()
    assert [m["periodo"] for m in mensual] == ["2026-09", "2026-10"]
    assert Decimal(mensual[1]["neto_cop"]) == Decimal("100000")
    assert api.get("/dashboard/ingresos/mensual?anio=2025").json() == []
    anual = api.get("/dashboard/ingresos/anual").json()
    assert anual[0]["periodo"] == "2026" and Decimal(anual[0]["bruto_cop"]) == Decimal("150000")


def test_endpoint_pedidos_filtra_por_mes_estado_y_cliente(api, db):
    cli = str(uuid.uuid4())
    a = pago(100000, codigo="ENV-A", cliente=cli, confirmado="2026-10-05T15:00:00Z")
    b = pago(200000, codigo="ENV-B", confirmado="2026-09-05T15:00:00Z")
    c = pago(300000, "pendiente", codigo="ENV-C")
    sincronizar(db, [a, b, c], [factura(a, "FP-00000001")])
    todos = api.get("/dashboard/ingresos/pedidos").json()
    assert {x["codigo_envio"] for x in todos} == {"ENV-A", "ENV-B", "ENV-C"}
    assert [x["codigo_envio"] for x in api.get("/dashboard/ingresos/pedidos?mes=2026-10").json()] == ["ENV-A"]
    assert [x["codigo_envio"] for x in api.get("/dashboard/ingresos/pedidos?estado=pendiente").json()] == ["ENV-C"]
    assert [x["codigo_envio"] for x in api.get(f"/dashboard/ingresos/pedidos?cliente_id={cli}").json()] == ["ENV-A"]
    assert api.get("/dashboard/ingresos/pedidos").json()[0]["factura_numero"] == "FP-00000001"


@pytest.mark.parametrize("query", ["mes=2026-13", "mes=octubre", "estado=otro", "limite=0", "limite=501"])
def test_endpoint_pedidos_valida_parametros(api, query):
    assert api.get(f"/dashboard/ingresos/pedidos?{query}").status_code == 422
