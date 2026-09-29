import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ResumenDiarioEntregasLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fecha: date
    total_creados: int
    total_entregados: int
    entregados_a_tiempo: int
    entregados_tarde: int
    con_incidencia: int
    devueltos: int
    tasa_cumplimiento_sla_pct: Optional[Decimal] = None


class UtilizacionFlotaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    vehiculo_id: uuid.UUID
    placa: str
    tipo: str
    en_uso: bool
    envio_id_actual: Optional[uuid.UUID] = None
    estado_envio_actual: Optional[str] = None
    actualizado_en: datetime


class EficienciaCombustibleConductorLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    conductor_id: uuid.UUID
    nombre_conductor: str
    vehiculo_id: Optional[uuid.UUID] = None
    placa_vehiculo: Optional[str] = None
    km_recorridos: Optional[Decimal] = None
    combustible_consumido_pct: Optional[Decimal] = None
    km_por_pct_combustible: Optional[Decimal] = None
    clasificacion: str
    lecturas_analizadas: int
    actualizado_en: datetime


class ProyeccionMantenimientoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    vehiculo_id: uuid.UUID
    placa_vehiculo: Optional[str] = None
    tipo_mantenimiento: str
    fecha_vencimiento: Optional[datetime] = None
    dias_restantes: Optional[int] = None
    kilometraje_vencimiento: Optional[Decimal] = None
    kilometraje_actual: Optional[Decimal] = None
    km_restantes: Optional[Decimal] = None
    prioridad_configurada: str
    urgencia: str
    actualizado_en: datetime


class CostoPorKmTipoVehiculoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tipo_vehiculo: str
    num_rutas_con_costo: int
    distancia_total_km: Decimal
    costo_total: Decimal
    costo_promedio_por_km: Optional[Decimal] = None
    actualizado_en: datetime


class ResumenEjecutivoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_vehiculos: int = 0
    vehiculos_en_uso: int = 0
    flota_disponible: int = 0
    total_conductores: int = 0
    total_envios_historico: int = 0
    envios_en_transito: int = 0
    envios_entregados_historico: int = 0
    envios_con_incidencia_historico: int = 0
    envios_internacionales_retenidos: int = 0
    tasa_cumplimiento_sla_global_pct: Optional[Decimal] = None
    facturacion_periodo_actual: Optional[Decimal] = None
    programas_mantenimiento_vencidos: int = 0
    ultima_actualizacion_etl: Optional[datetime] = None


class ActividadRecienteLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tipo_evento: str
    envio_id: Optional[uuid.UUID] = None
    vehiculo_id: Optional[uuid.UUID] = None
    mensaje: str
    ocurrido_en: datetime