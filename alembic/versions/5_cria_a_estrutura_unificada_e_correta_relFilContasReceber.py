"""Cria ou recria a tabela relFilContasReceber usando a melhor prática do Alembic.

Revision ID: 5
Revises: 4
Create Date: 2025-08-15 12:36:12.964070

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5'
down_revision: Union[str, Sequence[str], None] = '4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("--- GARANTINDO ESTRUTURA PADRONIZADA (MELHOR PRÁTICA) PARA a tabela relFilContasReceber ---")
    
    # 1. Apaga a tabela existente, se ela existir.
    print("-> Verificando e apagando a versão antiga da tabela (se existir)...")
    op.execute('DROP TABLE IF EXISTS "relFilContasReceber" CASCADE;')

    # 2. Cria a tabela do zero com a estrutura correta, usando op.create_table().
    print("-> Criando a nova tabela 'relFilContasReceber' com a estrutura correta...")
    op.create_table('relFilContasReceber',
        sa.Column('apartamento_id', sa.Integer(), nullable=False),
        sa.Column('chaveJurosDescontos', sa.Text(), nullable=True),
        sa.Column('cidCliente', sa.Text(), nullable=True),
        sa.Column('cidFilial', sa.Text(), nullable=True),
        sa.Column('codAcertoProprietario', sa.Integer(), nullable=True),
        sa.Column('codBaixa', sa.Integer(), nullable=True),
        sa.Column('codCliente', sa.Integer(), nullable=True),
        sa.Column('codDuplicataReceber', sa.Integer(), nullable=True),
        sa.Column('codEmpresas', sa.Integer(), nullable=True),
        sa.Column('codFatura', sa.Integer(), nullable=True),
        sa.Column('codFilial', sa.Integer(), nullable=True),
        sa.Column('codTransacao', sa.Integer(), nullable=True),
        sa.Column('dataEmissao', sa.TIMESTAMP(), nullable=True),
        sa.Column('dataPagto', sa.TIMESTAMP(), nullable=True),
        sa.Column('dataVenc', sa.TIMESTAMP(), nullable=True),
        sa.Column('descItemReceita', sa.Text(), nullable=True),
        sa.Column('descNegocio', sa.Text(), nullable=True),
        sa.Column('emailCliente', sa.Text(), nullable=True),
        sa.Column('historico', sa.Text(), nullable=True),
        sa.Column('historico1', sa.Text(), nullable=True),
        sa.Column('historico2', sa.Text(), nullable=True),
        sa.Column('jd', sa.Text(), nullable=True),
        sa.Column('listConhecimentos', sa.Text(), nullable=True),
        sa.Column('listDataEmissaoConhecimentos', sa.Text(), nullable=True),
        sa.Column('listNotas', sa.Text(), nullable=True),
        sa.Column('listaTiposFrete', sa.Text(), nullable=True),
        sa.Column('nomeCliente', sa.Text(), nullable=True),
        sa.Column('nomeEmpresas', sa.Text(), nullable=True),
        sa.Column('nomeFilial', sa.Text(), nullable=True),
        sa.Column('nomeFunc', sa.Text(), nullable=True),
        sa.Column('numContabil', sa.Integer(), nullable=True),
        sa.Column('numeroConta', sa.Text(), nullable=True),
        sa.Column('numeroContaFatura', sa.Text(), nullable=True),
        sa.Column('obs', sa.Text(), nullable=True),
        sa.Column('obsTransacao', sa.Text(), nullable=True),
        sa.Column('parcela', sa.Text(), nullable=True),
        sa.Column('tipoFatura', sa.Text(), nullable=True),
        sa.Column('ufCliente', sa.Text(), nullable=True),
        sa.Column('ufFilial', sa.Text(), nullable=True),
        sa.Column('valorPagto', sa.REAL(), nullable=True),
        sa.Column('valorVenc', sa.REAL(), nullable=True)
    )

def downgrade() -> None:
    print("--- REVERTENDO CRIAÇÃO DA TABELA relFilContasReceber ---")
    op.drop_table('relFilContasReceber')
