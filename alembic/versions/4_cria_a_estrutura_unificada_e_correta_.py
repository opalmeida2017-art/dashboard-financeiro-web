"""4_cria_a_estrutura_unificada_e_correta_relFilContasPagarDet

Revision ID: bba30895ad09
Revises: 3
Create Date: 2025-08-19 12:08:33.025763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bba30895ad09'
down_revision: Union[str, Sequence[str], None] = '3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.""""""Cria ou recria a tabela relFilContasPagarDet usando a melhor prática do Alembic.

Revision ID: 4
Revises: 3
Create Date: 2025-08-15 12:30:23.357271

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4'
down_revision: Union[str, Sequence[str], None] = '3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("--- GARANTINDO ESTRUTURA PADRONIZADA (MELHOR PRÁTICA) PARA a tabela relFilContasPagarDet ---")
    
    # 1. Apaga a tabela existente, se ela existir.
    print("-> Verificando e apagando a versão antiga da tabela (se existir)...")
    #op.execute('DROP TABLE IF EXISTS "relFilContasPagarDet" CASCADE;')

    # 2. Cria a tabela do zero com a estrutura correta, usando op.create_table().
    print("-> Criando a nova tabela 'relFilContasPagarDet' com a estrutura correta...")
    op.create_table('relFilContasPagarDet',
        sa.Column('apartamento_id', sa.Integer(), nullable=False),
        sa.Column('VED', sa.Text(), nullable=True),
        sa.Column('agencia', sa.Text(), nullable=True),
        sa.Column('banco', sa.Text(), nullable=True),
        sa.Column('chaveJurosDescontos', sa.Text(), nullable=True),
        sa.Column('chavePix', sa.Text(), nullable=True),
        sa.Column('cidFilial', sa.Text(), nullable=True),
        sa.Column('cidForn', sa.Text(), nullable=True),
        sa.Column('cnpjCpfForn', sa.Text(), nullable=True),
        sa.Column('codAcertoProprietario', sa.Integer(), nullable=True),
        sa.Column('codBaixa', sa.Integer(), nullable=True),
        sa.Column('codCheque', sa.Integer(), nullable=True),
        sa.Column('codDuplicataPagar', sa.Integer(), nullable=True),
        sa.Column('codEmpresas', sa.Integer(), nullable=True),
        sa.Column('codErpExterno', sa.Integer(), nullable=True),
        sa.Column('codFilial', sa.Integer(), nullable=True),
        sa.Column('codForn', sa.Integer(), nullable=True),
        sa.Column('codItemNota', sa.Integer(), nullable=True),
        sa.Column('codNota', sa.Integer(), nullable=True),
        sa.Column('codTipoPagto', sa.Integer(), nullable=True),
        sa.Column('codTransacao', sa.Integer(), nullable=True),
        sa.Column('codUnidadeEmbarque', sa.Integer(), nullable=True),
        sa.Column('contaForn', sa.Text(), nullable=True),
        sa.Column('dataEmissao', sa.TIMESTAMP(), nullable=True),
        sa.Column('dataLib', sa.TIMESTAMP(), nullable=True),
        sa.Column('dataPagto', sa.TIMESTAMP(), nullable=True),
        sa.Column('dataPagtoFormat', sa.TIMESTAMP(), nullable=True),
        sa.Column('dataPrevista', sa.TIMESTAMP(), nullable=True),
        sa.Column('dataVenc', sa.TIMESTAMP(), nullable=True),
        sa.Column('descGrupoD', sa.Text(), nullable=True),
        sa.Column('descItemD', sa.Text(), nullable=True),
        sa.Column('descTipoPagto', sa.Text(), nullable=True),
        sa.Column('descUnidadeEmbarque', sa.Text(), nullable=True),
        sa.Column('idTransacaoFretebras', sa.Text(), nullable=True),
        sa.Column('jd', sa.Text(), nullable=True),
        sa.Column('kmItemNota', sa.REAL(), nullable=True),
        sa.Column('liquidoItemNota', sa.REAL(), nullable=True),
        sa.Column('nomeEmpresas', sa.Text(), nullable=True),
        sa.Column('nomeFilial', sa.Text(), nullable=True),
        sa.Column('nomeForn', sa.Text(), nullable=True),
        sa.Column('numConhec', sa.Integer(), nullable=True),
        sa.Column('numNota', sa.Integer(), nullable=True),
        sa.Column('numeroConta', sa.Text(), nullable=True),
        sa.Column('numeroContaParcela', sa.Text(), nullable=True),
        sa.Column('obs', sa.Text(), nullable=True),
        sa.Column('obsFaturaCompra', sa.Text(), nullable=True),
        sa.Column('obsTransacao', sa.Text(), nullable=True),
        sa.Column('parcela', sa.Text(), nullable=True),
        sa.Column('pesoSaidaMotorista', sa.REAL(), nullable=True),
        sa.Column('placaVeiculo', sa.Text(), nullable=True),
        sa.Column('premioSeguro', sa.REAL(), nullable=True),
        sa.Column('quantidadeItemNota', sa.REAL(), nullable=True),
        sa.Column('serie', sa.Text(), nullable=True),
        sa.Column('superGrupoD', sa.Text(), nullable=True),
        sa.Column('totalTipoPagto', sa.REAL(), nullable=True),
        sa.Column('ufFilial', sa.Text(), nullable=True),
        sa.Column('ufForn', sa.Text(), nullable=True),
        sa.Column('usuarioINS', sa.Text(), nullable=True),
        sa.Column('usuarioLib', sa.Text(), nullable=True),
        sa.Column('valorIcmsNota', sa.REAL(), nullable=True),
        sa.Column('valorImpSfedNota', sa.REAL(), nullable=True),
        sa.Column('valorIssNota', sa.REAL(), nullable=True),
        sa.Column('valorNota', sa.REAL(), nullable=True),
        sa.Column('valorPagto', sa.REAL(), nullable=True),
        sa.Column('valorProporcional', sa.REAL(), nullable=True),
        sa.Column('valorQuebra', sa.REAL(), nullable=True),
        sa.Column('valorVenc', sa.REAL(), nullable=True),
        sa.Column('vlCofinsRetNota', sa.REAL(), nullable=True),
        sa.Column('vlCsllRetNota', sa.REAL(), nullable=True),
        sa.Column('vlFat', sa.REAL(), nullable=True),
        sa.Column('vlInssRetNota', sa.REAL(), nullable=True),
        sa.Column('vlIrrfRetNota', sa.REAL(), nullable=True),
        sa.Column('vlPisRetNota', sa.REAL(), nullable=True)
    )

def downgrade() -> None:
    print("--- REVERTENDO CRIAÇÃO DA TABELA relFilContasPagarDet ---")
    op.drop_table('relFilContasPagarDet')
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
