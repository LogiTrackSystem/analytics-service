"""Ingresos por pedido, mes y año (COP), a partir de los pagos y facturas por pedido de Billing.

Criterio contable (simple y explícito):
- Ingreso bruto de un mes = pagos cobrados (estado confirmado o reembolsado) según el mes de su confirmación.
- Reembolsos de un mes = pagos reembolsados según el mes del reembolso.
- Ingreso neto = bruto - reembolsos. Un pago pendiente no es ingreso.
- Los meses se calculan en hora de Colombia (UTC-5 fijo, sin horario de verano).
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Awaitable, Callable, Optional

from sqlalchemy.orm import Session

from .models import IngresoPedido

COLOMBIA = timezone(timedelta(hours=-5))
PAGINA = 500
MAX_PAGINAS = 200
CERO = Decimal("0.00")


def _a_dt(valor) -> Optional[datetime]:
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def mes_colombia(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(COLOMBIA).strftime("%Y-%m")


def _dec(valor) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"))


async def _paginar(get_json: Callable[..., Awaitable], url: str) -> Optional[list]:
    """Descarga todas las páginas. Devuelve None si alguna falla: en ese caso NO se debe reconstruir
    la tabla, para no borrar los ingresos por una caída transitoria de Billing."""
    filas: list = []
    for pagina in range(MAX_PAGINAS):
        datos = await get_json(url, params={"limite": PAGINA, "offset": pagina * PAGINA}, default=None)
        if datos is None:
            return None
        filas.extend(datos)
        if len(datos) < PAGINA:
            return filas
    return filas


async def sincronizar_ingresos(db: Session, base_billing_url: str, get_json) -> dict:
    """Reconstruye `ingresos_pedido` desde Billing. Devuelve un resumen para el resultado del ETL."""
    pagos = await _paginar(get_json, f"{base_billing_url}/pagos/")
    facturas = await _paginar(get_json, f"{base_billing_url}/facturas-pedido/")
    if pagos is None or facturas is None:
        return {"actualizado": False, "motivo": "Billing no respondió; se conserva la última versión"}

    factura_por_pago = {f["pago_id"]: f for f in facturas}
    nuevas = []
    for p in pagos:
        try:
            monto = _dec(p["monto_cop"])
        except Exception:
            print(f"[analytics-ingresos] pago ignorado por monto inválido: {p.get('id')}")
            continue
        confirmado = _a_dt(p.get("confirmado_en"))
        reembolsado = _a_dt(p.get("reembolsado_en"))
        factura = factura_por_pago.get(p["id"]) or {}
        nuevas.append(IngresoPedido(
            pago_id=uuid.UUID(str(p["id"])), envio_id=uuid.UUID(str(p["envio_id"])),
            codigo_envio=p.get("codigo_envio"), cliente_id=uuid.UUID(str(p["cliente_id"])), monto_cop=monto, estado_pago=p["estado"],
            factura_numero=factura.get("numero"), factura_estado=factura.get("estado"),
            confirmado_en=confirmado, reembolsado_en=reembolsado,
            mes_pago=mes_colombia(confirmado), mes_reembolso=mes_colombia(reembolsado),
        ))

    db.query(IngresoPedido).delete(synchronize_session=False)
    db.add_all(nuevas)
    db.commit()
    return {"actualizado": True, "pagos": len(nuevas)}


def ingresos_por_mes(db: Session, anio: Optional[int] = None) -> list[dict]:
    """Una fila por mes con actividad, ordenada de más antiguo a más reciente."""
    meses: dict[str, dict] = {}

    def fila(periodo):
        return meses.setdefault(periodo, {
            "periodo": periodo, "pedidos_cobrados": 0, "bruto_cop": CERO,
            "pedidos_reembolsados": 0, "reembolsos_cop": CERO,
        })

    for monto, estado, mes_pago, mes_reembolso in db.query(
        IngresoPedido.monto_cop, IngresoPedido.estado_pago, IngresoPedido.mes_pago, IngresoPedido.mes_reembolso
    ).all():
        monto = Decimal(str(monto))
        if estado in ("confirmado", "reembolsado") and mes_pago:
            f = fila(mes_pago)
            f["pedidos_cobrados"] += 1
            f["bruto_cop"] += monto
        if estado == "reembolsado" and mes_reembolso:
            f = fila(mes_reembolso)
            f["pedidos_reembolsados"] += 1
            f["reembolsos_cop"] += monto

    salida = []
    for periodo in sorted(meses):
        if anio is not None and not periodo.startswith(f"{anio}-"):
            continue
        f = meses[periodo]
        f["neto_cop"] = f["bruto_cop"] - f["reembolsos_cop"]
        f["ticket_promedio_cop"] = (
            (f["bruto_cop"] / f["pedidos_cobrados"]).quantize(Decimal("0.01")) if f["pedidos_cobrados"] else None
        )
        salida.append(f)
    return salida


def ingresos_por_anio(db: Session) -> list[dict]:
    anios: dict[str, dict] = {}
    for m in ingresos_por_mes(db):
        a = anios.setdefault(m["periodo"][:4], {
            "periodo": m["periodo"][:4], "pedidos_cobrados": 0, "bruto_cop": CERO,
            "pedidos_reembolsados": 0, "reembolsos_cop": CERO,
        })
        a["pedidos_cobrados"] += m["pedidos_cobrados"]
        a["bruto_cop"] += m["bruto_cop"]
        a["pedidos_reembolsados"] += m["pedidos_reembolsados"]
        a["reembolsos_cop"] += m["reembolsos_cop"]
    for a in anios.values():
        a["neto_cop"] = a["bruto_cop"] - a["reembolsos_cop"]
        a["ticket_promedio_cop"] = (
            (a["bruto_cop"] / a["pedidos_cobrados"]).quantize(Decimal("0.01")) if a["pedidos_cobrados"] else None
        )
    return [anios[k] for k in sorted(anios)]


def neto_del_periodo(db: Session, ahora: Optional[datetime] = None) -> tuple[Decimal, Decimal]:
    """(neto del mes en curso, neto del año en curso), hora de Colombia."""
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(COLOMBIA)
    mes, anio = ahora.strftime("%Y-%m"), ahora.strftime("%Y")
    neto_mes = next((m["neto_cop"] for m in ingresos_por_mes(db) if m["periodo"] == mes), CERO)
    neto_anio = next((a["neto_cop"] for a in ingresos_por_anio(db) if a["periodo"] == anio), CERO)
    return neto_mes, neto_anio
