"""Unitaria 1: ingresos.ingresos_por_mes suma lo cobrado, resta reembolsos e ignora pagos pendientes."""
import uuid
from decimal import Decimal

from app.ingresos import ingresos_por_mes
from app.models import IngresoPedido


def _ingreso(monto, estado, mes_pago, mes_reembolso=None):
    return IngresoPedido(pago_id=uuid.uuid4(), envio_id=uuid.uuid4(), cliente_id=uuid.uuid4(),
                         monto_cop=monto, estado_pago=estado, mes_pago=mes_pago, mes_reembolso=mes_reembolso)


def test_ingresos_por_mes_calcula_bruto_reembolsos_y_neto(db):
    db.add_all([_ingreso(200000, "confirmado", "2026-10"),
                _ingreso(100000, "reembolsado", "2026-10", "2026-10"),
                _ingreso(50000, "pendiente", None)])
    db.commit()
    octubre = ingresos_por_mes(db)[0]
    assert octubre["periodo"] == "2026-10" and octubre["pedidos_cobrados"] == 2
    assert octubre["bruto_cop"] == Decimal("300000") and octubre["neto_cop"] == Decimal("200000")
