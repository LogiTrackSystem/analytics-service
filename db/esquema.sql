-- Esquema de analytics_db (analytics-service): SQL generado por 'alembic upgrade head --sql' a partir de alembic/versions.
-- Crea todas las tablas, secuencias y restricciones. No contiene datos.
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> ddd78afe6d3f

CREATE TABLE actividad_reciente (
    id UUID NOT NULL, 
    tipo_evento VARCHAR(30) NOT NULL, 
    envio_id UUID, 
    vehiculo_id UUID, 
    mensaje VARCHAR(300) NOT NULL, 
    ocurrido_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE INDEX ix_actividad_reciente_ocurrido_en ON actividad_reciente (ocurrido_en);

CREATE TABLE costo_por_km_tipo_vehiculo (
    id UUID NOT NULL, 
    tipo_vehiculo VARCHAR(50) NOT NULL, 
    num_rutas_con_costo INTEGER NOT NULL, 
    distancia_total_km NUMERIC(12, 2) NOT NULL, 
    costo_total NUMERIC(14, 2) NOT NULL, 
    costo_promedio_por_km NUMERIC(12, 2), 
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_costo_por_km_tipo_vehiculo_tipo_vehiculo ON costo_por_km_tipo_vehiculo (tipo_vehiculo);

CREATE TABLE eficiencia_combustible_conductor (
    id UUID NOT NULL, 
    conductor_id UUID NOT NULL, 
    nombre_conductor VARCHAR(150) NOT NULL, 
    vehiculo_id UUID, 
    placa_vehiculo VARCHAR(10), 
    km_recorridos NUMERIC(10, 2), 
    combustible_consumido_pct NUMERIC(5, 2), 
    km_por_pct_combustible NUMERIC(10, 2), 
    clasificacion VARCHAR(20) NOT NULL, 
    lecturas_analizadas INTEGER NOT NULL, 
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_eficiencia_combustible_conductor_conductor_id ON eficiencia_combustible_conductor (conductor_id);

CREATE TABLE proyeccion_mantenimiento (
    id UUID NOT NULL, 
    programa_id UUID NOT NULL, 
    vehiculo_id UUID NOT NULL, 
    placa_vehiculo VARCHAR(10), 
    tipo_mantenimiento VARCHAR(50) NOT NULL, 
    fecha_vencimiento TIMESTAMP WITH TIME ZONE, 
    dias_restantes INTEGER, 
    kilometraje_vencimiento NUMERIC(10, 2), 
    kilometraje_actual NUMERIC(10, 2), 
    km_restantes NUMERIC(10, 2), 
    prioridad_configurada VARCHAR(20) NOT NULL, 
    urgencia VARCHAR(25) NOT NULL, 
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_proyeccion_mantenimiento_programa_id ON proyeccion_mantenimiento (programa_id);

CREATE INDEX ix_proyeccion_mantenimiento_vehiculo_id ON proyeccion_mantenimiento (vehiculo_id);

CREATE TABLE resumen_diario_entregas (
    id UUID NOT NULL, 
    fecha DATE NOT NULL, 
    total_creados INTEGER NOT NULL, 
    total_entregados INTEGER NOT NULL, 
    entregados_a_tiempo INTEGER NOT NULL, 
    entregados_tarde INTEGER NOT NULL, 
    con_incidencia INTEGER NOT NULL, 
    devueltos INTEGER NOT NULL, 
    tasa_cumplimiento_sla_pct NUMERIC(5, 2), 
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_resumen_diario_entregas_fecha ON resumen_diario_entregas (fecha);

CREATE TABLE resumen_ejecutivo (
    clave VARCHAR(20) NOT NULL, 
    total_vehiculos INTEGER NOT NULL, 
    vehiculos_en_uso INTEGER NOT NULL, 
    flota_disponible INTEGER NOT NULL, 
    total_conductores INTEGER NOT NULL, 
    total_envios_historico INTEGER NOT NULL, 
    envios_en_transito INTEGER NOT NULL, 
    envios_entregados_historico INTEGER NOT NULL, 
    envios_con_incidencia_historico INTEGER NOT NULL, 
    envios_internacionales_retenidos INTEGER NOT NULL, 
    tasa_cumplimiento_sla_global_pct NUMERIC(5, 2), 
    facturacion_periodo_actual NUMERIC(14, 2), 
    programas_mantenimiento_vencidos INTEGER NOT NULL, 
    ultima_actualizacion_etl TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (clave)
);

CREATE TABLE utilizacion_flota (
    id UUID NOT NULL, 
    vehiculo_id UUID NOT NULL, 
    placa VARCHAR(10) NOT NULL, 
    tipo VARCHAR(50) NOT NULL, 
    en_uso BOOLEAN NOT NULL, 
    envio_id_actual UUID, 
    estado_envio_actual VARCHAR(20), 
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_utilizacion_flota_vehiculo_id ON utilizacion_flota (vehiculo_id);

INSERT INTO alembic_version (version_num) VALUES ('ddd78afe6d3f') RETURNING alembic_version.version_num;

-- Running upgrade ddd78afe6d3f -> a1c5e9b3d702

CREATE TABLE ingresos_pedido (
    id UUID NOT NULL, 
    pago_id UUID NOT NULL, 
    envio_id UUID NOT NULL, 
    codigo_envio VARCHAR(20), 
    cliente_id UUID NOT NULL, 
    monto_cop NUMERIC(14, 2) NOT NULL, 
    estado_pago VARCHAR(15) NOT NULL, 
    factura_numero VARCHAR(20), 
    factura_estado VARCHAR(15), 
    confirmado_en TIMESTAMP WITH TIME ZONE, 
    reembolsado_en TIMESTAMP WITH TIME ZONE, 
    mes_pago VARCHAR(7), 
    mes_reembolso VARCHAR(7), 
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_ingresos_pedido_pago_id ON ingresos_pedido (pago_id);

CREATE INDEX ix_ingresos_pedido_envio_id ON ingresos_pedido (envio_id);

CREATE INDEX ix_ingresos_pedido_cliente_id ON ingresos_pedido (cliente_id);

CREATE INDEX ix_ingresos_pedido_mes_pago ON ingresos_pedido (mes_pago);

CREATE INDEX ix_ingresos_pedido_mes_reembolso ON ingresos_pedido (mes_reembolso);

ALTER TABLE resumen_ejecutivo ADD COLUMN ingresos_mes_actual_cop NUMERIC(16, 2);

ALTER TABLE resumen_ejecutivo ADD COLUMN ingresos_anio_actual_cop NUMERIC(16, 2);

UPDATE alembic_version SET version_num='a1c5e9b3d702' WHERE alembic_version.version_num = 'ddd78afe6d3f';

COMMIT;

