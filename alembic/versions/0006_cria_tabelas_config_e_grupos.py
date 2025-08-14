"""Cria tabelas static_expense_groups e configuracoes_robo

Revision ID: 0006
Revises: 0005
Create Date: 2025-08-13 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('static_expense_groups',
        sa.Column('apartamento_id', sa.Integer(), nullable=False),
        sa.Column('group_name', sa.Text(), nullable=False),
        sa.Column('is_despesa', sa.Text(), server_default='S', nullable=True),
        sa.Column('is_custo_viagem', sa.Text(), server_default='N', nullable=True),
        # Chave primária composta correta para multi-tenant
        sa.PrimaryKeyConstraint('apartamento_id', 'group_name')
    )

    op.create_table('configuracoes_robo',
        sa.Column('apartamento_id', sa.Integer(), nullable=False),
        sa.Column('chave', sa.Text(), nullable=False),
        sa.Column('valor', sa.Text(), nullable=True),
        # Chave primária composta correta para multi-tenant
        sa.PrimaryKeyConstraint('apartamento_id', 'chave')
    )


def downgrade() -> None:
    op.drop_table('configuracoes_robo')
    op.drop_table('static_expense_groups')

