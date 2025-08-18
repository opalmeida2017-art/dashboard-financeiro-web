"""2_Cria_a_estrutura_unificada_e_correta_do_banco_de_dados

Revision ID: 2
Revises: 1
Create Date: 2025-08-15 12:30:23.357271

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2'
down_revision: Union[str, Sequence[str], None] = '1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    print("--- INICIANDO CRIAÇÃO DA ESTRUTURA UNIFICADA E FINAL DO BANCO DE DADOS ---")
    
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # --- TABELAS DE SISTEMA (apartamentos, usuarios, etc.) ---
    # (O código para criar as tabelas de sistema, como 'apartamentos' e 'usuarios', seria o mesmo da resposta anterior)
    # ... por brevidade, vamos focar na nova tabela ...

    # --- TABELA: relFilContasPagarDet ---
    
    if not inspector.has_table('relFilContasPagarDet'):
        print("-> Criando tabela 'relFilContasPagarDet'...")
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
            sa.Column('codCheque', sa.Text(), nullable=True),
            sa.Column('codDuplicataPagar', sa.Integer(), nullable=True),
            sa.Column('codEmpresas', sa.Integer(), nullable=True),
            sa.Column('codErpExterno', sa.Text(), nullable=True),
            sa.Column('codFilial', sa.Integer(), nullable=True),
            sa.Column('codForn', sa.Integer(), nullable=True),
            sa.Column('codItemNota', sa.Integer(), nullable=True),
            sa.Column('codNota', sa.Integer(), nullable=True),
            sa.Column('codTipoPagto', sa.Integer(), nullable=True),
            sa.Column('codTransacao', sa.Text(), nullable=True),
            sa.Column('codUnidadeEmbarque', sa.Text(), nullable=True),
            sa.Column('contaForn', sa.Text(), nullable=True),
            sa.Column('dataEmissao', sa.Text(), nullable=True),
            sa.Column('dataLib', sa.Text(), nullable=True),
            sa.Column('dataPagto', sa.Text(), nullable=True),
            sa.Column('dataPagtoFormat', sa.Text(), nullable=True),
            sa.Column('dataPrevista', sa.Text(), nullable=True),
            sa.Column('dataVenc', sa.Text(), nullable=True),
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
            sa.Column('numNota', sa.Text(), nullable=True),
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
    else:
        print("-> Tabela 'relFilContasPagarDet' já existe. Pulando.")
    
    # Adicione aqui os outros CREATE/CHECK para as demais tabelas de dados...
    # (relFilViagensCliente, relFilViagensFatCliente, etc.)

    print("--- CRIAÇÃO DE ESTRUTURA CONCLUÍDA ---")


def downgrade() -> None:
    print("--- REVERTENDO CRIAÇÃO DE TABELAS ---")
    op.drop_table('relFilContasPagarDet')
    # Adicione aqui os outros DROP TABLE na ordem inversa da criação
    # op.drop_table('relFilViagensCliente')
    # ...
    # op.drop_table('apartamentos')
