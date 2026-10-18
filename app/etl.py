import os
from datetime import datetime, timezone, timedelta

import httpx
from .interno import cabeceras_internas
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import (
    UtilizacionFlota, EficienciaCombustibleConductor, ProyeccionMantenimiento,
    CostoPorKmTipoVehiculo, ResumenEjecutivo, ResumenDiarioEntregas,
)
from .ingresos import sincronizar_ingresos, neto_del_periodo

FLEET_SERVICE_URL = os.getenv("FLEET_SERVICE_URL")
SHIPMENT_SERVICE_URL = os.getenv("SHIPMENT_SERVICE_URL")
ROUTING_SERVICE_URL = os.getenv("ROUTING_SERVICE_URL")
TRACKING_SERVICE_URL = os.getenv("TRACKING_SERVICE_URL")
MAINTENANCE_SERVICE_URL = os.getenv("MAINTENANCE_SERVICE_URL")
CUSTOMS_SERVICE_URL = os.getenv("CUSTOMS_SERVICE_URL")
BILLING_SERVICE_URL = os.getenv("BILLING_SERVICE_URL")

VENTANA_TELEMETRIA_DIAS = 7


async def _get_json(url: str, params: dict | None = None, default=None):
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=cabeceras_internas()) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        print(f"[analytics-etl] fallo consultando {url}: {exc}")
        return default


def _parse_dt(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except Exception:
        return None


async def _calcular_telemetria_por_vehiculo(vehiculo_id: str):
    desde = (datetime.now(timezone.utc) - timedelta(days=VENTANA_TELEMETRIA_DIAS)).isoformat()
    lecturas = await _get_json(
        f"{TRACKING_SERVICE_URL}/telemetria/{vehiculo_id}",
        params={"desde": desde, "limite": 500},
        default=[],
    ) or []

    if len(lecturas) < 2:
        return {"km_recorridos": None, "combustible_consumido_pct": None, "km_por_pct": None,
                "avg_km_dia": None, "ultimo_km": None, "lecturas": len(lecturas)}

    ordenadas = sorted(lecturas, key=lambda x: x["tiempo"])
    primero, ultimo = ordenadas[0], ordenadas[-1]

    km_ini, km_fin = primero.get("kilometraje_acumulado_km"), ultimo.get("kilometraje_acumulado_km")
    km_recorridos = max(0.0, float(km_fin) - float(km_ini)) if km_ini is not None and km_fin is not None else None

    t_ini, t_fin = _parse_dt(primero["tiempo"]), _parse_dt(ultimo["tiempo"])
    dias_span = max((t_fin - t_ini).total_seconds() / 86400, 0.01) if t_ini and t_fin else None
    avg_km_dia = (km_recorridos / dias_span) if (km_recorridos is not None and dias_span) else None

    fuel_ini, fuel_fin = primero.get("nivel_combustible_pct"), ultimo.get("nivel_combustible_pct")
    combustible_consumido = (
        max(0.0, float(fuel_ini) - float(fuel_fin)) if fuel_ini is not None and fuel_fin is not None else None
    )

    km_por_pct = None
    if km_recorridos and combustible_consumido and combustible_consumido > 0:
        km_por_pct = km_recorridos / combustible_consumido

    return {
        "km_recorridos": km_recorridos,
        "combustible_consumido_pct": combustible_consumido,
        "km_por_pct": km_por_pct,
        "avg_km_dia": avg_km_dia,
        "ultimo_km": float(km_fin) if km_fin is not None else None,
        "lecturas": len(lecturas),
    }


async def _actualizar_utilizacion_flota(db: Session, vehiculos, envios, rutas):
    envio_por_id = {e["id"]: e for e in envios}
    ruta_actual_por_vehiculo = {}
    for r in rutas:  # ya vienen ordenadas por creado_en desc
        vid = r.get("vehiculo_id")
        if vid and vid not in ruta_actual_por_vehiculo:
            ruta_actual_por_vehiculo[vid] = r

    db.query(UtilizacionFlota).delete(synchronize_session=False)

    en_uso_count = 0
    for v in vehiculos:
        ruta = ruta_actual_por_vehiculo.get(v["id"])
        en_uso, envio_id_actual, estado_envio = False, None, None
        if ruta:
            envio = envio_por_id.get(ruta.get("envio_id"))
            if envio and envio.get("estado") in ("pendiente", "en_transito"):
                en_uso, envio_id_actual, estado_envio = True, envio["id"], envio["estado"]
        if en_uso:
            en_uso_count += 1
        db.add(UtilizacionFlota(
            vehiculo_id=v["id"], placa=v["placa"], tipo=v["tipo"],
            en_uso=en_uso, envio_id_actual=envio_id_actual, estado_envio_actual=estado_envio,
        ))
    db.commit()
    return en_uso_count


async def _actualizar_costo_por_km(db: Session, rutas):
    costos = await _get_json(f"{BILLING_SERVICE_URL}/costos-ruta/", default=[]) or []
    ruta_por_id = {r["id"]: r for r in rutas}
    vehiculo_cache = {}

    agregados = {}
    for c in costos:
        ruta = ruta_por_id.get(c.get("ruta_id"))
        if not ruta or not ruta.get("vehiculo_id"):
            continue
        vehiculo_id = ruta["vehiculo_id"]
        if vehiculo_id not in vehiculo_cache:
            vehiculo_cache[vehiculo_id] = await _get_json(f"{FLEET_SERVICE_URL}/vehiculos/{vehiculo_id}")
        vehiculo = vehiculo_cache[vehiculo_id]
        if not vehiculo:
            continue
        tipo = vehiculo["tipo"]
        agr = agregados.setdefault(tipo, {"num": 0, "distancia": 0.0, "costo": 0.0})
        agr["num"] += 1
        agr["distancia"] += float(c.get("distancia_km") or 0)
        agr["costo"] += float(c.get("costo_total") or 0)

    db.query(CostoPorKmTipoVehiculo).delete(synchronize_session=False)
    for tipo, agr in agregados.items():
        promedio = (agr["costo"] / agr["distancia"]) if agr["distancia"] > 0 else None
        db.add(CostoPorKmTipoVehiculo(
            tipo_vehiculo=tipo, num_rutas_con_costo=agr["num"],
            distancia_total_km=round(agr["distancia"], 2), costo_total=round(agr["costo"], 2),
            costo_promedio_por_km=round(promedio, 2) if promedio is not None else None,
        ))
    db.commit()


async def _actualizar_eficiencia_y_mantenimiento(db: Session, vehiculos, conductores):
    conductor_por_vehiculo = {d["vehiculo_id"]: d for d in conductores if d.get("vehiculo_id")}

    telemetria_por_vehiculo = {}
    for v in vehiculos:
        telemetria_por_vehiculo[v["id"]] = await _calcular_telemetria_por_vehiculo(v["id"])

    # --- eficiencia de combustible por conductor ---
    filas = []
    for vehiculo_id, conductor in conductor_por_vehiculo.items():
        vehiculo = next((v for v in vehiculos if v["id"] == vehiculo_id), None)
        stats = telemetria_por_vehiculo.get(vehiculo_id, {})
        filas.append({
            "conductor_id": conductor["id"],
            "nombre_conductor": conductor["nombre"],
            "vehiculo_id": vehiculo_id,
            "placa_vehiculo": vehiculo["placa"] if vehiculo else None,
            "km_recorridos": stats.get("km_recorridos"),
            "combustible_consumido_pct": stats.get("combustible_consumido_pct"),
            "km_por_pct_combustible": stats.get("km_por_pct"),
            "lecturas_analizadas": stats.get("lecturas", 0),
        })

    validos = sorted(
        [f for f in filas if f["km_por_pct_combustible"] is not None],
        key=lambda f: f["km_por_pct_combustible"],
    )
    n = len(validos)
    for i, f in enumerate(validos):
        if n < 3:
            f["clasificacion"] = "normal"
        elif i < n / 3:
            f["clasificacion"] = "ineficiente"
        elif i < 2 * n / 3:
            f["clasificacion"] = "normal"
        else:
            f["clasificacion"] = "eficiente"
    for f in filas:
        f.setdefault("clasificacion", "sin_datos")

    db.query(EficienciaCombustibleConductor).delete(synchronize_session=False)
    for f in filas:
        db.add(EficienciaCombustibleConductor(**f))
    db.commit()

    # --- proyección de mantenimiento (90 días) ---
    db.query(ProyeccionMantenimiento).delete(synchronize_session=False)
    hoy = datetime.now(timezone.utc).date()
    vencidos_count = 0
    for v in vehiculos:
        programas = await _get_json(f"{MAINTENANCE_SERVICE_URL}/programas/{v['id']}", default=[]) or []
        stats = telemetria_por_vehiculo.get(v["id"], {})
        for p in programas:
            dias_restantes = None
            if p.get("fecha_vencimiento"):
                fecha = _parse_dt(p["fecha_vencimiento"])
                if fecha:
                    dias_restantes = (fecha.date() - hoy).days

            km_restantes = None
            if p.get("kilometraje_vencimiento") is not None and stats.get("ultimo_km") is not None:
                km_restantes = float(p["kilometraje_vencimiento"]) - stats["ultimo_km"]
                if dias_restantes is None and stats.get("avg_km_dia"):
                    dias_restantes = int(km_restantes / stats["avg_km_dia"])

            if dias_restantes is None:
                urgencia = "sin_datos_suficientes"
            elif dias_restantes <= 0:
                urgencia = "vencido"
            elif dias_restantes <= 15:
                urgencia = "critico"
            elif dias_restantes <= 90:
                urgencia = "proximo"
            else:
                urgencia = "programado"

            if urgencia == "vencido":
                vencidos_count += 1

            db.add(ProyeccionMantenimiento(
                programa_id=p["id"], vehiculo_id=v["id"], placa_vehiculo=v["placa"],
                tipo_mantenimiento=p["tipo"],
                fecha_vencimiento=_parse_dt(p.get("fecha_vencimiento")),
                dias_restantes=dias_restantes,
                kilometraje_vencimiento=p.get("kilometraje_vencimiento"),
                kilometraje_actual=stats.get("ultimo_km"),
                km_restantes=km_restantes,
                prioridad_configurada=p.get("prioridad", "media"),
                urgencia=urgencia,
            ))
    db.commit()
    return vencidos_count


async def _construir_resumen_ejecutivo(db: Session, vehiculos, conductores, envios, en_uso_count, vencidos_count):
    declaraciones_retenidas = await _get_json(
        f"{CUSTOMS_SERVICE_URL}/declaraciones/", params={"estado": "retenido"}, default=[]
    ) or []
    periodo_actual = datetime.now(timezone.utc).strftime("%Y-%m")
    facturas = await _get_json(
        f"{BILLING_SERVICE_URL}/facturas/", params={"periodo": periodo_actual}, default=[]
    ) or []
    facturacion_total = sum(float(f.get("monto_total") or 0) for f in facturas)

    filas_resumen = db.query(ResumenDiarioEntregas).all()
    total_a_tiempo = sum(r.entregados_a_tiempo for r in filas_resumen)
    total_entregados_hist = sum(r.total_entregados for r in filas_resumen)
    tasa_global = round((total_a_tiempo / total_entregados_hist) * 100, 2) if total_entregados_hist else None

    resumen = db.query(ResumenEjecutivo).filter(ResumenEjecutivo.clave == "actual").first()
    if resumen is None:
        resumen = ResumenEjecutivo(clave="actual")
        db.add(resumen)

    resumen.total_vehiculos = len(vehiculos)
    resumen.vehiculos_en_uso = en_uso_count
    resumen.flota_disponible = len(vehiculos) - en_uso_count
    resumen.total_conductores = len(conductores)
    resumen.total_envios_historico = len(envios)
    resumen.envios_en_transito = sum(1 for e in envios if e.get("estado") == "en_transito")
    resumen.envios_entregados_historico = sum(1 for e in envios if e.get("estado") == "entregado")
    resumen.envios_con_incidencia_historico = sum(1 for e in envios if e.get("estado") == "con_incidencia")
    resumen.envios_internacionales_retenidos = len(declaraciones_retenidas)
    resumen.tasa_cumplimiento_sla_global_pct = tasa_global
    resumen.facturacion_periodo_actual = round(facturacion_total, 2)
    resumen.programas_mantenimiento_vencidos = vencidos_count
    resumen.ingresos_mes_actual_cop, resumen.ingresos_anio_actual_cop = neto_del_periodo(db)
    resumen.ultima_actualizacion_etl = datetime.now(timezone.utc)
    db.commit()


async def ejecutar_ciclo_etl():
    db: Session = SessionLocal()
    resultado = {"ok": True, "detalles": {}}
    try:
        vehiculos = await _get_json(f"{FLEET_SERVICE_URL}/vehiculos/", default=[]) or []
        conductores = await _get_json(f"{FLEET_SERVICE_URL}/conductores/", default=[]) or []
        envios = await _get_json(f"{SHIPMENT_SERVICE_URL}/envios/", default=[]) or []
        rutas = await _get_json(f"{ROUTING_SERVICE_URL}/rutas/", default=[]) or []

        en_uso_count = await _actualizar_utilizacion_flota(db, vehiculos, envios, rutas)
        await _actualizar_costo_por_km(db, rutas)
        detalle_ingresos = await sincronizar_ingresos(db, BILLING_SERVICE_URL, _get_json)
        vencidos_count = await _actualizar_eficiencia_y_mantenimiento(db, vehiculos, conductores)
        await _construir_resumen_ejecutivo(db, vehiculos, conductores, envios, en_uso_count, vencidos_count)

        resultado["detalles"] = {
            "vehiculos_procesados": len(vehiculos),
            "envios_procesados": len(envios),
            "vehiculos_en_uso": en_uso_count,
            "programas_vencidos": vencidos_count,
            "ingresos": detalle_ingresos,
        }
    except Exception as exc:
        resultado["ok"] = False
        resultado["error"] = str(exc)
        print(f"[analytics-etl] ciclo fallido: {exc}")
    finally:
        db.close()
    return resultado