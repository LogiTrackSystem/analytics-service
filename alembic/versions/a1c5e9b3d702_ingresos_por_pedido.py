"""ingresos por pedido: tabla ingresos_pedido y totales de ingresos en resumen_ejecutivo

Revision ID: a1c5e9b3d702
Revises: ddd78afe6d3f
Create Date: 2026-10-18 12:00:00.000000

Solo agrega: una tabla nueva y dos columnas nullable. No borra ni modifica datos existentes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c5e9b3d702'
down_revision: Union[str, Sequence[str], None] = 'ddd78afe6d3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ingresos_pedido',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('pago_id', sa.UUID(), nullable=False),
        sa.Column('envio_id', sa.UUID(), nullable=False),
        sa.Column('codigo_envio', sa.String(length=20), nullable=True),
        sa.Column('cliente_id', sa.UUID(), nullable=False),
        sa.Column('monto_cop', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('estado_pago', sa.String(length=15), nullable=False),
        sa.Column('factura_numero', sa.String(length=20), nullable=True),
        sa.Column('factura_estado', sa.String(length=15), nullable=True),
        sa.Column('confirmado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reembolsado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mes_pago', sa.String(length=7), nullable=True),
        sa.Column('mes_reembolso', sa.String(length=7), nullable=True),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ingresos_pedido_pago_id'), 'ingresos_pedido', ['pago_id'], unique=True)
    op.create_index(op.f('ix_ingresos_pedido_envio_id'), 'ingresos_pedido', ['envio_id'], unique=False)
    op.create_index(op.f('ix_ingresos_pedido_cliente_id'), 'ingresos_pedido', ['cliente_id'], unique=False)
    op.create_index(op.f('ix_ingresos_pedido_mes_pago'), 'ingresos_pedido', ['mes_pago'], unique=False)
    op.create_index(op.f('ix_ingresos_pedido_mes_reembolso'), 'ingresos_pedido', ['mes_reembolso'], unique=False)
    op.add_column('resumen_ejecutivo', sa.Column('ingresos_mes_actual_cop', sa.Numeric(precision=16, scale=2), nullable=True))
    op.add_column('resumen_ejecutivo', sa.Column('ingresos_anio_actual_cop', sa.Numeric(precision=16, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('resumen_ejecutivo', 'ingresos_anio_actual_cop')
    op.drop_column('resumen_ejecutivo', 'ingresos_mes_actual_cop')
    op.drop_index(op.f('ix_ingresos_pedido_mes_reembolso'), table_name='ingresos_pedido')
    op.drop_index(op.f('ix_ingresos_pedido_mes_pago'), table_name='ingresos_pedido')
    op.drop_index(op.f('ix_ingresos_pedido_cliente_id'), table_name='ingresos_pedido')
    op.drop_index(op.f('ix_ingresos_pedido_envio_id'), table_name='ingresos_pedido')
    op.drop_index(op.f('ix_ingresos_pedido_pago_id'), table_name='ingresos_pedido')
    op.drop_table('ingresos_pedido')
