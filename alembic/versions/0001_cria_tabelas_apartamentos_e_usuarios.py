"""Cria tabelas apartamentos e usuarios

Revision ID: 0001
Revises: 
Create Date: 2025-08-13 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('apartamentos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome_empresa', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default='ativo', nullable=True),
        sa.Column('data_criacao', sa.Text(), nullable=False),
        sa.Column('data_vencimento', sa.Text(), nullable=True),
        sa.Column('notas_admin', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('usuarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('apartamento_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('nome', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), server_default='usuario', nullable=True),
        sa.ForeignKeyConstraint(['apartamento_id'], ['apartamentos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )


def downgrade() -> None:
    op.drop_table('usuarios')
    op.drop_table('apartamentos')