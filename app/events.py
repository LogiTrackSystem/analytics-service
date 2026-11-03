import json
import os
import uuid
from datetime import datetime, timezone

import aio_pika
import httpx
from .interno import cabeceras_internas
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import ResumenDiarioEntregas, ActividadReciente

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
SHIPMENT_SERVICE_URL = os.getenv("SHIPMENT_SERVICE_URL")
EXCHANGE_NAME = "logitrack_events"

ROUTING_KEYS = [
    "shipment.created",
    "shipment.delivered",
    "shipment.incident",
    "shipment.returned",
    "route.assigned",
    "maintenance.alert",
    "customs.held",
    "customs.cleared",
]


def _a_uuid(valor):
    if not valor:
        return None
    try:
        return uuid.UUID(str(valor))
    except Exception:
        return None


async def _obtener_envio(envio_id: str):
    if not SHIPMENT_SERVICE_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=cabeceras_internas()) as client:
            resp = await client.get(f"{SHIPMENT_SERVICE_URL}/envios/{envio_id}")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


def _obtener_o_crear_resumen_hoy(db: Session) -> ResumenDiarioEntregas:
    hoy = datetime.now(timezone.utc).date()
    resumen = db.query(ResumenDiarioEntregas).filter(ResumenDiarioEntregas.fecha == hoy).first()
    if resumen is None:
        resumen = ResumenDiarioEntregas(fecha=hoy)
        db.add(resumen)
        db.commit()
        db.refresh(resumen)
    return resumen


def _registrar_actividad(db: Session, tipo_evento: str, mensaje: str, envio_id=None, vehiculo_id=None):
    db.add(ActividadReciente(
        tipo_evento=tipo_evento,
        envio_id=_a_uuid(envio_id),
        vehiculo_id=_a_uuid(vehiculo_id),
        mensaje=mensaje,
    ))
    db.commit()


async def _procesar_shipment_created(payload: dict):
    db: Session = SessionLocal()
    try:
        resumen = _obtener_o_crear_resumen_hoy(db)
        resumen.total_creados += 1
        db.commit()
        _registrar_actividad(
            db, "shipment.created",
            f"Nuevo envío creado: {payload.get('origen')} → {payload.get('destino')}",
            envio_id=payload.get("envio_id"),
        )
    finally:
        db.close()


async def _procesar_shipment_delivered(payload: dict):
    db: Session = SessionLocal()
    try:
        envio_id = payload.get("envio_id")
        entregado_en_str = payload.get("entregado_en")
        envio = await _obtener_envio(envio_id)

        a_tiempo = True
        if envio and envio.get("fecha_limite_sla") and entregado_en_str:
            try:
                entregado_en = datetime.fromisoformat(str(entregado_en_str).replace("Z", "+00:00"))
                fecha_limite = datetime.fromisoformat(str(envio["fecha_limite_sla"]).replace("Z", "+00:00"))
                a_tiempo = entregado_en <= fecha_limite
            except Exception:
                a_tiempo = True

        resumen = _obtener_o_crear_resumen_hoy(db)
        resumen.total_entregados += 1
        if a_tiempo:
            resumen.entregados_a_tiempo += 1
        else:
            resumen.entregados_tarde += 1
        if resumen.total_entregados:
            resumen.tasa_cumplimiento_sla_pct = round(
                (resumen.entregados_a_tiempo / resumen.total_entregados) * 100, 2
            )
        db.commit()

        etiqueta = "a tiempo" if a_tiempo else "con retraso"
        _registrar_actividad(
            db, "shipment.delivered",
            f"Envío entregado a {payload.get('nombre_receptor', 'receptor')} ({etiqueta})",
            envio_id=envio_id,
        )
    finally:
        db.close()


async def _procesar_shipment_incident(payload: dict):
    db: Session = SessionLocal()
    try:
        resumen = _obtener_o_crear_resumen_hoy(db)
        resumen.con_incidencia += 1
        db.commit()
        _registrar_actividad(
            db, "shipment.incident",
            f"Incidencia reportada: {payload.get('notas') or 'sin detalle'}",
            envio_id=payload.get("envio_id"),
        )
    finally:
        db.close()


async def _procesar_shipment_returned(payload: dict):
    db: Session = SessionLocal()
    try:
        resumen = _obtener_o_crear_resumen_hoy(db)
        resumen.devueltos += 1
        db.commit()
        _registrar_actividad(
            db, "shipment.returned",
            f"Envío devuelto: {payload.get('notas') or 'sin detalle'}",
            envio_id=payload.get("envio_id"),
        )
    finally:
        db.close()


async def _procesar_route_assigned(payload: dict):
    db: Session = SessionLocal()
    try:
        _registrar_actividad(
            db, "route.assigned",
            f"Ruta asignada para el envío {payload.get('envio_id')}",
            envio_id=payload.get("envio_id"),
            vehiculo_id=payload.get("vehiculo_id"),
        )
    finally:
        db.close()


async def _procesar_maintenance_alert(payload: dict):
    db: Session = SessionLocal()
    try:
        motivo = payload.get("motivo", "desconocido")
        _registrar_actividad(
            db, "maintenance.alert",
            f"Alerta de mantenimiento ({motivo}) para el vehículo {payload.get('vehiculo_id')}",
            vehiculo_id=payload.get("vehiculo_id"),
        )
    finally:
        db.close()


async def _procesar_customs_held(payload: dict):
    db: Session = SessionLocal()
    try:
        _registrar_actividad(
            db, "customs.held",
            f"Envío retenido en aduana ({payload.get('pais_origen')} → {payload.get('pais_destino')}): "
            f"{payload.get('motivo_retencion', 'sin motivo especificado')}",
            envio_id=payload.get("envio_id"),
        )
    finally:
        db.close()


async def _procesar_customs_cleared(payload: dict):
    db: Session = SessionLocal()
    try:
        _registrar_actividad(
            db, "customs.cleared",
            f"Envío liberado de aduana ({payload.get('pais_origen')} → {payload.get('pais_destino')})",
            envio_id=payload.get("envio_id"),
        )
    finally:
        db.close()


_HANDLERS = {
    "shipment.created": _procesar_shipment_created,
    "shipment.delivered": _procesar_shipment_delivered,
    "shipment.incident": _procesar_shipment_incident,
    "shipment.returned": _procesar_shipment_returned,
    "route.assigned": _procesar_route_assigned,
    "maintenance.alert": _procesar_maintenance_alert,
    "customs.held": _procesar_customs_held,
    "customs.cleared": _procesar_customs_cleared,
}


async def _on_message(message: aio_pika.IncomingMessage):
    async with message.process():
        payload = json.loads(message.body.decode())
        handler = _HANDLERS.get(message.routing_key)
        if handler:
            await handler(payload)


async def iniciar_consumidor():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue("analytics_service.eventos", durable=True)
    for routing_key in ROUTING_KEYS:
        await queue.bind(exchange, routing_key=routing_key)
    await queue.consume(_on_message)
    return connection