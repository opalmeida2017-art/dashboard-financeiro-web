"""Cria ou recria as tabelas de sistema para garantir a estrutura correta.

Revision ID: 1
Revises: 
Create Date: 2025-08-19 10:51:19.616369

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("--- GARANTINDO ESTRUTURA PADRONIZADA PARA AS TABELAS DE SISTEMA ---")
    
    # --- INÍCIO DA CORREÇÃO ---
    
    # 1. Apaga todas as tabelas de sistema na ordem inversa para lidar com dependências (usuários depende de apartamentos).
    #    'CASCADE' garante que objetos dependentes sejam removidos sem erros.
    print("-> Verificando e apagando versões antigas das tabelas de sistema...")
    #op.execute('DROP TABLE IF EXISTS "configuracoes_robo" CASCADE;')
    #op.execute('DROP TABLE IF EXISTS "static_expense_groups" CASCADE;')
    #op.execute('DROP TABLE IF EXISTS "usuarios" CASCADE;')
    #op.execute('DROP TABLE IF EXISTS "apartamentos" CASCADE;')

    # 2. Recria todas as tabelas do zero com a estrutura correta, na ordem correta.
    print("-> Criando as novas tabelas de sistema com a estrutura correta...")
    
    op.create_table('apartamentos',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('nome_empresa', sa.Text(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=True, unique=True),
        sa.Column('status', sa.Text(), server_default='ativo', nullable=True),
        sa.Column('data_criacao', sa.Text(), nullable=False),
        sa.Column('data_vencimento', sa.Text(), nullable=True),
        sa.Column('notas_admin', sa.Text(), nullable=True)
    )

    op.create_table('usuarios',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('apartamento_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False, unique=True),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('nome', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), server_default='usuario', nullable=True),
        sa.ForeignKeyConstraint(['apartamento_id'], ['apartamentos.id'])
    )

    op.create_table('static_expense_groups',
        sa.Column('apartamento_id', sa.Integer(), nullable=False),
        sa.Column('group_name', sa.Text(), nullable=False),
        sa.Column('is_despesa', sa.Text(), server_default='S', nullable=True),
        sa.Column('is_custo_viagem', sa.Text(), server_default='N', nullable=True),
        sa.PrimaryKeyConstraint('apartamento_id', 'group_name')
    )

    op.create_table('configuracoes_robo',
        sa.Column('apartamento_id', sa.Integer(), nullable=False),
        sa.Column('chave', sa.Text(), nullable=False),
        sa.Column('valor', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('apartamento_id', 'chave')
    )
    
    # --- FIM DA CORREÇÃO ---

    print("--- CRIAÇÃO DAS TABELAS DE SISTEMA CONCLUÍDA ---")


def downgrade() -> None:
    print("--- REVERTENDO CRIAÇÃO DAS TABELAS DE SISTEMA ---")
    op.drop_table('static_expense_groups')
    op.drop_table('configuracoes_robo')
    op.drop_table('usuarios')
    op.drop_table('apartamentos')