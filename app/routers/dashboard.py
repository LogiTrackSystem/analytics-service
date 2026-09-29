from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    ResumenDiarioEntregas, UtilizacionFlota, EficienciaCombustibleConductor,
    ProyeccionMantenimiento, CostoPorKmTipoVehiculo, ResumenEjecutivo, ActividadReciente,
)
from ..schemas import (
    ResumenDiarioEntregasLeer, UtilizacionFlotaLeer, EficienciaCombustibleConductorLeer,
    ProyeccionMantenimientoLeer, CostoPorKmTipoVehiculoLeer, ResumenEjecutivoLeer, ActividadRecienteLeer,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/resumen", response_model=ResumenEjecutivoLeer)
def obtener_resumen(db: Session = Depends(get_db)):
    resumen = db.query(ResumenEjecutivo).filter(ResumenEjecutivo.clave == "actual").first()
    if resumen is None:
        return ResumenEjecutivoLeer()
    return resumen


@router.get("/entregas-diarias", response_model=list[ResumenDiarioEntregasLeer])
def obtener_entregas_diarias(dias: int = Query(30, le=365), db: Session = Depends(get_db)):
    desde = date.today() - timedelta(days=dias)
    return (
        db.query(ResumenDiarioEntregas)
        .filter(ResumenDiarioEntregas.fecha >= desde)
        .order_by(ResumenDiarioEntregas.fecha.asc())
        .all()
    )


@router.get("/utilizacion-flota", response_model=list[UtilizacionFlotaLeer])
def obtener_utilizacion_flota(db: Session = Depends(get_db)):
    return db.query(UtilizacionFlota).order_by(UtilizacionFlota.placa.asc()).all()


@router.get("/costo-por-km", response_model=list[CostoPorKmTipoVehiculoLeer])
def obtener_costo_por_km(db: Session = Depends(get_db)):
    return db.query(CostoPorKmTipoVehiculo).order_by(CostoPorKmTipoVehiculo.tipo_vehiculo.asc()).all()


@router.get("/eficiencia-combustible", response_model=list[EficienciaCombustibleConductorLeer])
def obtener_eficiencia_combustible(limite: int = Query(50, le=200), db: Session = Depends(get_db)):
    return (
        db.query(EficienciaCombustibleConductor)
        .order_by(EficienciaCombustibleConductor.km_por_pct_combustible.asc().nullslast())
        .limit(limite)
        .all()
    )


@router.get("/proyeccion-mantenimiento", response_model=list[ProyeccionMantenimientoLeer])
def obtener_proyeccion_mantenimiento(
    dias: int = Query(90, le=3650), todos: bool = False, db: Session = Depends(get_db)
):
    query = db.query(ProyeccionMantenimiento)
    if not todos:
        query = query.filter(
            or_(ProyeccionMantenimiento.dias_restantes.is_(None), ProyeccionMantenimiento.dias_restantes <= dias)
        )
    return query.order_by(ProyeccionMantenimiento.dias_restantes.asc().nullslast()).all()


@router.get("/actividad-reciente", response_model=list[ActividadRecienteLeer])
def obtener_actividad_reciente(limite: int = Query(20, le=200), db: Session = Depends(get_db)):
    return (
        db.query(ActividadReciente)
        .order_by(ActividadReciente.ocurrido_en.desc())
        .limit(limite)
        .all()
    )