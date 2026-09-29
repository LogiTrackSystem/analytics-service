import uuid
from sqlalchemy import Column, String, Boolean, Integer, Numeric, Date, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from .database import Base


class ResumenDiarioEntregas(Base):
    """Tabla histórica/incremental: alimentada por eventos, nunca se borra."""
    __tablename__ = "resumen_diario_entregas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fecha = Column(Date, nullable=False, unique=True, index=True)
    total_creados = Column(Integer, nullable=False, default=0)
    total_entregados = Column(Integer, nullable=False, default=0)
    entregados_a_tiempo = Column(Integer, nullable=False, default=0)
    entregados_tarde = Column(Integer, nullable=False, default=0)
    con_incidencia = Column(Integer, nullable=False, default=0)
    devueltos = Column(Integer, nullable=False, default=0)
    tasa_cumplimiento_sla_pct = Column(Numeric(5, 2), nullable=True)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UtilizacionFlota(Base):
    """Snapshot: se borra y reconstruye por completo en cada ciclo de ETL."""
    __tablename__ = "utilizacion_flota"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehiculo_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    placa = Column(String(10), nullable=False)
    tipo = Column(String(50), nullable=False)
    en_uso = Column(Boolean, nullable=False, default=False)
    envio_id_actual = Column(UUID(as_uuid=True), nullable=True)
    estado_envio_actual = Column(String(20), nullable=True)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EficienciaCombustibleConductor(Base):
    """Snapshot: se borra y reconstruye por completo en cada ciclo de ETL."""
    __tablename__ = "eficiencia_combustible_conductor"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conductor_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    nombre_conductor = Column(String(150), nullable=False)
    vehiculo_id = Column(UUID(as_uuid=True), nullable=True)
    placa_vehiculo = Column(String(10), nullable=True)
    km_recorridos = Column(Numeric(10, 2), nullable=True)
    combustible_consumido_pct = Column(Numeric(5, 2), nullable=True)
    km_por_pct_combustible = Column(Numeric(10, 2), nullable=True)
    clasificacion = Column(String(20), nullable=False, default="sin_datos")
    lecturas_analizadas = Column(Integer, nullable=False, default=0)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProyeccionMantenimiento(Base):
    """Snapshot: se borra y reconstruye por completo en cada ciclo de ETL."""
    __tablename__ = "proyeccion_mantenimiento"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    programa_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    vehiculo_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    placa_vehiculo = Column(String(10), nullable=True)
    tipo_mantenimiento = Column(String(50), nullable=False)
    fecha_vencimiento = Column(DateTime(timezone=True), nullable=True)
    dias_restantes = Column(Integer, nullable=True)
    kilometraje_vencimiento = Column(Numeric(10, 2), nullable=True)
    kilometraje_actual = Column(Numeric(10, 2), nullable=True)
    km_restantes = Column(Numeric(10, 2), nullable=True)
    prioridad_configurada = Column(String(20), nullable=False, default="media")
    urgencia = Column(String(25), nullable=False, default="sin_datos_suficientes")
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CostoPorKmTipoVehiculo(Base):
    """Snapshot: se borra y reconstruye por completo en cada ciclo de ETL."""
    __tablename__ = "costo_por_km_tipo_vehiculo"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_vehiculo = Column(String(50), nullable=False, unique=True, index=True)
    num_rutas_con_costo = Column(Integer, nullable=False, default=0)
    distancia_total_km = Column(Numeric(12, 2), nullable=False, default=0)
    costo_total = Column(Numeric(14, 2), nullable=False, default=0)
    costo_promedio_por_km = Column(Numeric(12, 2), nullable=True)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResumenEjecutivo(Base):
    """Snapshot de una sola fila: los números grandes del dashboard."""
    __tablename__ = "resumen_ejecutivo"

    clave = Column(String(20), primary_key=True, default="actual")
    total_vehiculos = Column(Integer, nullable=False, default=0)
    vehiculos_en_uso = Column(Integer, nullable=False, default=0)
    flota_disponible = Column(Integer, nullable=False, default=0)
    total_conductores = Column(Integer, nullable=False, default=0)
    total_envios_historico = Column(Integer, nullable=False, default=0)
    envios_en_transito = Column(Integer, nullable=False, default=0)
    envios_entregados_historico = Column(Integer, nullable=False, default=0)
    envios_con_incidencia_historico = Column(Integer, nullable=False, default=0)
    envios_internacionales_retenidos = Column(Integer, nullable=False, default=0)
    tasa_cumplimiento_sla_global_pct = Column(Numeric(5, 2), nullable=True)
    facturacion_periodo_actual = Column(Numeric(14, 2), nullable=True)
    programas_mantenimiento_vencidos = Column(Integer, nullable=False, default=0)
    ultima_actualizacion_etl = Column(DateTime(timezone=True), nullable=True)


class ActividadReciente(Base):
    """Tabla histórica/incremental: feed en vivo, alimentado por eventos."""
    __tablename__ = "actividad_reciente"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_evento = Column(String(30), nullable=False)
    envio_id = Column(UUID(as_uuid=True), nullable=True)
    vehiculo_id = Column(UUID(as_uuid=True), nullable=True)
    mensaje = Column(String(300), nullable=False)
    ocurrido_en = Column(DateTime(timezone=True), server_default=func.now(), index=True)