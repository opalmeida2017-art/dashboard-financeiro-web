"""Cria_a_estrutura_unificada_e_correta_do_banco_de_dados

Revision ID: 1
Revises: 
Create Date: 2025-08-15 11:25:46.725153

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
    print("--- INICIANDO CRIAÇÃO/VERIFICAÇÃO DA ESTRUTURA UNIFICADA DE TABELAS ---")
    
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # --- TABELAS DE SISTEMA ---
    
    if not inspector.has_table('apartamentos'):
        print("-> Criando tabela 'apartamentos'...")
        op.create_table('apartamentos',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('nome_empresa', sa.Text(), nullable=False),
            sa.Column('status', sa.Text(), server_default='ativo', nullable=True),
            sa.Column('data_criacao', sa.Text(), nullable=False),
            sa.Column('data_vencimento', sa.Text(), nullable=True),
            sa.Column('notas_admin', sa.Text(), nullable=True)
        )

    if not inspector.has_table('usuarios'):
        print("-> Criando tabela 'usuarios'...")
        op.create_table('usuarios',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('apartamento_id', sa.Integer(), nullable=False),
            sa.Column('email', sa.Text(), nullable=False, unique=True),
            sa.Column('password_hash', sa.Text(), nullable=False),
            sa.Column('nome', sa.Text(), nullable=True),
            sa.Column('role', sa.Text(), server_default='usuario', nullable=True),
            sa.ForeignKeyConstraint(['apartamento_id'], ['apartamentos.id'])
        )

    if not inspector.has_table('static_expense_groups'):
        print("-> Criando tabela 'static_expense_groups'...")
        op.create_table('static_expense_groups',
            sa.Column('apartamento_id', sa.Integer(), nullable=False),
            sa.Column('group_name', sa.Text(), nullable=False),
            sa.Column('is_despesa', sa.Text(), server_default='S', nullable=True),
            sa.Column('is_custo_viagem', sa.Text(), server_default='N', nullable=True),
            sa.PrimaryKeyConstraint('apartamento_id', 'group_name')
        )

    if not inspector.has_table('configuracoes_robo'):
        print("-> Criando tabela 'configuracoes_robo'...")
        op.create_table('configuracoes_robo',
            sa.Column('apartamento_id', sa.Integer(), nullable=False),
            sa.Column('chave', sa.Text(), nullable=False),
            sa.Column('valor', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('apartamento_id', 'chave')
        )

    # --- TABELAS DE DADOS (USANDO SQL PURO PARA GARANTIR COMPATIBILIDADE) ---

    if not inspector.has_table('relFilViagensCliente'):
        print("-> Criando tabela 'relFilViagensCliente'...")
        op.execute("""
            CREATE TABLE "relFilViagensCliente" (
                apartamento_id INTEGER NOT NULL, "acertoICMS" TEXT, "acertoSaldo" REAL, "adValor" REAL, 
                "adiantamentoMotorista" REAL, "adtoMot2" REAL, "aliquotaCofins" REAL, "aliquotaIss" REAL, 
                "aliquotaPis" REAL, "arqXMLAss" TEXT, "baseICMS" REAL, "baseICMSDireta" TEXT, 
                "baseImpostos" REAL, "baseIss" REAL, cancelado TEXT, "cargaDescarga" REAL, 
                "cartaFrete" TEXT, "celularMotorista" TEXT, "celularProp" TEXT, "chaveNF" TEXT, 
                "checkList" TEXT, "cidDestinoFormat" TEXT, "cidOrigemFormat" TEXT, "cnhMotorista" TEXT, 
                "cnpjCpfCliente" TEXT, "cnpjCpfDest" TEXT, "cnpjCpfEmpresas" TEXT, "cnpjCpfFilial" TEXT, 
                "cnpjCpfProp" TEXT, "cnpjCpfRemet" TEXT, "cnpjUnidadeEmb" TEXT, "codClDest" INTEGER, 
                "codClRemet" INTEGER, "codCliente" INTEGER, "codColetaEntregaAg" INTEGER, "codEmpresas" INTEGER, 
                "codFaturaSaldo" INTEGER, "codFilial" INTEGER, "codMercadoria" INTEGER, "codOrdemCar" INTEGER, 
                "codProp" INTEGER, "codRota" INTEGER, "codServicoNfs" INTEGER, "codUnidadeEmb" INTEGER, 
                comissao REAL, "cpfMotorista" TEXT, "cteChave" TEXT, "cteDataReciboEnv" TEXT, 
                "cteFusoHorarioAutor" TEXT, "cteProt" TEXT, "cteStatus" TEXT, "dataALT" TEXT, 
                "dataEmissao" TEXT, "dataEmissaoComHora" TEXT, "dataINS" TEXT, "dataNascimentoProp" TEXT, 
                "dataPrevDescarga" TEXT, "dataPrevEntrega" TEXT, "dataViagemMotorista" TEXT, "descAg" TEXT, 
                "descEntrega" TEXT, "descTipoCte" TEXT, "descontaICMSSaldoEmpresa" TEXT, "descontaINSSSaldoMot" TEXT, 
                "descricaoEspecieMerc" TEXT, "descricaoMercadoria" TEXT, "despesaExtra" REAL, 
                despesasadicionais REAL, "embarcadorNome" TEXT, "envioLote" TEXT, "estadiaEmbutidaFrete" TEXT, 
                "fTotalPrest" REAL, "faturaICMSFinal" REAL, "faturaPesoChegada" REAL, "foneMotorista" TEXT, 
                "foneProp" TEXT, "freteEmpresa" REAL, "freteEmpresaSai" REAL, "freteMotorista" REAL, 
                "freteMotoristaSai" REAL, "fretePago" TEXT, "horaFimDescarga" TEXT, "icmsEmbutido" TEXT, 
                "inscricaoEstadualFilial" TEXT, "margemFrete" REAL, "margemFretePerc" REAL, modelo TEXT, 
                natureza TEXT, "nfseProt" TEXT, "nfseStatus" TEXT, "nfseStatusDesc" TEXT, 
                "nomeCidCliente" TEXT, "nomeCidDestino" TEXT, "nomeCidOrigem" TEXT, "nomeClDest" TEXT, 
                "nomeClRemet" TEXT, "nomeCliente" TEXT, "nomeEmpresas" TEXT, "nomeFilial" TEXT, 
                "nomeMotorista" TEXT, "nomeProp" TEXT, "nomeUnidEmb" TEXT, "numConhec" INTEGER, 
                "numConhecColEntrega" TEXT, "numNF" TEXT, "numNotaNF" TEXT, "numPedido" TEXT, numero TEXT, 
                "numeroApolice" TEXT, "numeroColEntrega" TEXT, obs TEXT, "obsFaturaPeso" TEXT, 
                "obsFiscal" TEXT, "outrosDescontos" REAL, "outrosDescontosMot" REAL, "outrosDescontosMot2" REAL, 
                "pagaICMS" TEXT, "pagaISS" TEXT, pagar TEXT, "pedagioEmbFreteMot" TEXT, 
                "pedagioEmbutido" TEXT, "pedagioEmbutidoFrete" TEXT, "pedidoCliente2" TEXT, "pedidoFrete" TEXT, 
                "pedidoTransf" TEXT, "percRedVLICMS" REAL, "permiteFaturar" TEXT, "permitePagarSaldoFrota" TEXT, 
                "pesoChegada" REAL, "pesoSaida" REAL, "pesoSaidaMotorista" REAL, "pisProp" TEXT, 
                "placaVeiculo" TEXT, "porcICMS" REAL, "precoKgMercQuebra" REAL, "precoMercadoria" REAL, 
                "precoTonEmpresa" REAL, "precoTonFiscal" REAL, "precoTonMotorista" REAL, "premioSeguro" REAL, 
                "premioSeguro2" REAL, "quantMercadoria" REAL, "quantidadeQuebra" REAL, "quebraSegurada" TEXT, 
                "quebraTotal" REAL, "rgMotorista" TEXT, "sacaCarRPapel" TEXT, "saldoMotorista" REAL, 
                "secCatEmbutidoFrete" TEXT, "serieCte" TEXT, "serieNF" TEXT, "taxaQuebra" REAL, 
                tempo TEXT, "tempoAtraso" TEXT, "tempoPrev" TEXT, "tempoTransp" TEXT, "tipoDesconto" TEXT, 
                "tipoFrete" TEXT, "tipoTolerancia" TEXT, "tipoTributacao" TEXT, "toleranciaPesoCheg" REAL, 
                "tributaImpostos" TEXT, "ufCliente" TEXT, "ufDestino" TEXT, "ufOrigem" TEXT, 
                "usuarioALT" TEXT, "usuarioINS" TEXT, "valorAbonoQuebra" REAL, "valorBalsa" REAL, 
                "valorClassificacao" REAL, "valorCofins" REAL, "valorEstadia" REAL, "valorFreteFiscal" REAL, 
                "valorICMS" REAL, "valorINSS" REAL, "valorIRRF" REAL, "valorIss" REAL, 
                "valorMercadoria" REAL, "valorPedagio" REAL, "valorPis" REAL, "valorQuebra" REAL, 
                "valorSeguro" REAL, "valorSeguro2" REAL, "valorSestSenat" REAL, "valorTotalnf" REAL, 
                "versaoCte" TEXT, "vlTotalPrestacaoDacte" REAL, "adiantamentoEmpresa" REAL, "cidadeClientePrincipal" TEXT,
                "dataVencSaldo" TEXT, "descSeguroSaldoMot" REAL, "freteEmpresaComp" REAL, "numeroConhecimento" INTEGER,
                "saldoEmp" REAL, "vlIcms" REAL
            );
        """)
    else:
        print("-> Tabela 'relFilViagensCliente' já existe. Pulando.")
    
    # Adicione aqui os outros CREATE TABLE IF NOT EXISTS para as demais tabelas de dados...

    print("--- CRIAÇÃO DE ESTRUTURA CONCLUÍDA ---")


def downgrade() -> None:
    print("--- REVERTENDO CRIAÇÃO DE TABELAS (ESTRUTURA COMPLETA) ---")
    op.drop_table('relFilContasPagarDet')
    op.drop_table('relFilContasReceber')
    op.drop_table('relFilDespesasGerais')
    op.drop_table('relFilViagensFatCliente')
    op.drop_table('relFilViagensCliente')
    op.drop_table('static_expense_groups')
    op.drop_table('configuracoes_robo')
    op.drop_table('usuarios')
    op.drop_table('apartamentos')
