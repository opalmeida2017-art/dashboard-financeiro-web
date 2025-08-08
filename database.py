import os
import psycopg2
import sqlite3
import pandas as pd
import config
import glob 
from datetime import datetime



DATABASE_NAME = 'financeiro.db'

def get_db_connection():
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        try:
            return psycopg2.connect(db_url)
        except psycopg2.Error as e:
            print(f"Erro ao conectar ao PostgreSQL: {e}")
            return None
    else:
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            print(f"Erro ao conectar ao banco de dados SQLite: {e}")
            return None

def create_tables():
    """Cria TODAS as tabelas do banco de dados com o esquema definitivo."""
    with get_db_connection() as conn:
        if conn is None:
            return
        cursor = conn.cursor()
        print("Verificando e criando esquema do banco de dados com nomes exatos...")

        # Nomes de tabelas e colunas são colocados entre aspas para preservar maiúsculas/minúsculas.
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "relFilViagensFatCliente" (
                "COFINS" REAL, "CSLL" REAL, "PIS" REAL, "acertoSaldo" REAL, "adiantamentoEmp2" REAL, "adiantamentoEmpresa" REAL,
                "adiantamentoMotorista" REAL, "adtoMot2" REAL, "agregado" TEXT, "baseISS" REAL, "cargaDescarga" REAL,
                "cepCliente" TEXT, "cidCliente" TEXT, "cidDest" TEXT, "cidEmpresas" TEXT, "cidOrig" TEXT, "cidadeClientePrincipal" TEXT,
                "cidadeDest" TEXT, "cidadeFil" TEXT, "cidadeRem" TEXT, "classificacaoEmbFreteEmp" TEXT, "clientePagaSaldoMotorista" TEXT,
                "cnpjCpfCliente" TEXT, "cnpjCpfEmpresas" TEXT, "cnpjCpfFil" TEXT, "cnpjCpfProp" TEXT, "codAcertoProprietario" INTEGER,
                "codCheque" TEXT, "codCliente" INTEGER, "codClientePrincipal" INTEGER, "codDest" INTEGER, "codFatPagAdiant" INTEGER,
                "codFatPagSaldo" INTEGER, "codFaturaAdiantEmp2" INTEGER, "codFaturaAdiantamento" INTEGER, "codFaturaClassificacao" INTEGER,
                "codFaturaEstadia" INTEGER, "codFaturaICMS" INTEGER, "codFaturaPedagio" INTEGER, "codFaturaSaldo" INTEGER,
                "codFaturaSaldoComp" INTEGER, "codFilial" INTEGER, "codFornecedorAdiant" INTEGER, "codFornecedorClassificacao" INTEGER,
                "codFornecedorICMS" INTEGER, "codFornecedorPedagio" INTEGER, "codFornecedorSaldo" INTEGER, "codManif" INTEGER,
                "codMercadoria" INTEGER, "codProp" INTEGER, "codRem" INTEGER, "codTipoCliente" INTEGER, "codTransAdiant" INTEGER,
                "codTransEstadia" INTEGER, "codTransICMS" INTEGER, "codTransPedagio" INTEGER, "codTransSaldo" INTEGER,
                "codVeiculo" INTEGER, "complementoCliente" TEXT, "contrato" TEXT, "cpfMot" TEXT, "cteDataReciboEnv" TEXT,
                "cteStatus" TEXT, "cteStatusDesc" TEXT, "dataChegouSaldo" TEXT, "dataEmissao" TEXT, "dataEncerramento" TEXT,
                "dataFatPagAdiant" TEXT, "dataFatPagSaldo" TEXT, "dataFatSaldo" TEXT, "dataINS" TEXT, "dataNascimentoMot" TEXT,
                "dataPagtoDuplicatas" TEXT, "dataPrevDescarga" TEXT, "dataVencAdiant" TEXT, "dataVencSaldo" TEXT,
                "dataViagemMotorista" TEXT, "descCSLLSaldoEmp" REAL, "descCofinsSaldoEmp" REAL, "descColeta" REAL,
                "descDifFrete" REAL, "descEntrega" REAL, "descIRRFSaldoEmp" REAL, "descPISSaldoEmp" REAL, "descPedagioBaseMot" REAL,
                "descQuebraSaldoEmp" TEXT, "descSeguro2Saldo" REAL, "descSeguro2SaldoMot" REAL, "descSeguroSaldo" REAL,
                "descSeguroSaldoMot" REAL, "descSestSenatSaldoEmp" REAL, "descontaICMSSaldoEmpresa" TEXT,
                "descontaINSSSaldo" TEXT, "descontaINSSSaldoMot" TEXT, "descontaISSSaldoEmp" TEXT, "descricaoMercadoria" TEXT,
                "despesaExtra" REAL, "enderecoCliente" TEXT, "enderecoEmpresas" TEXT, "enderecoFil" TEXT, "estadiaEmbutidaFrete" TEXT,
                "fEmp" REAL, "faturaICMSFinal" REAL, "faturaPesoChegada" REAL, "faturamento" REAL, "faxEmpresas" TEXT,
                "faxFil" TEXT, "foneCliente" TEXT, "foneEmpresas" TEXT, "foneFil" TEXT, "freteCombinado" REAL, "freteEmpresa" REAL,
                "freteEmpresaComp" REAL, "freteEmpresaSai" REAL, "freteMotorista" REAL, "freteMotoristaSai" REAL,
                "historico1FatSaldo" TEXT, "historico2FatSaldo" TEXT, "historicoFatSaldo" TEXT, "horaFimDescarga" TEXT,
                "icmsEmbutido" TEXT, "inscEstCliente" TEXT, "issEmbutido" TEXT, "kmFim" REAL, "kmIni" REAL, "kmParc" REAL,
                "kmRodado" REAL, "liberadoOrdServ" TEXT, "nomeCliente" TEXT, "nomeClientePrincipal" TEXT, "nomeDest" TEXT,
                "nomeEmpresas" TEXT, "nomeFilial" TEXT, "nomeFornSaldo" TEXT, "nomeMot" TEXT, "nomeProp" TEXT, "nomeRem" TEXT,
                "numConhec" INTEGER, "numNF" TEXT, "numPedido" TEXT, "numero" TEXT, "numeroClassificacao" TEXT, "numeroICMS" TEXT,
                "numeroProgramacao" TEXT, "obsFatSaldo" TEXT, "outrosDescontos" REAL, "outrosDescontosMot" REAL,
                "outrosDescontosMot2" REAL, "pagaICMS" TEXT, "pedagioEmbutidoFrete" TEXT, "pedidoFrete" TEXT,
                "percRedVLICMS" REAL, "permiteFaturar" TEXT, "permitePagarSaldoFrota" TEXT, "pesoChegada" REAL,
                "pesoSaida" REAL, "pesoSaidaMotorista" REAL, "placa" TEXT, "precoTonEmpresa" REAL, "precoTonMotorista" REAL,
                "premioSeguro" REAL, "premioSeguro2" REAL, "quantMercadoria" REAL, "quantidadeQuebra" REAL,
                "quebraSegurada" TEXT, "saldoEmp" REAL, "saldoMotorista" REAL, "somaFreteEmpresaComICMS" REAL,
                "somarISSFatSaldo" TEXT, "taxaAdiantEmpresa" REAL, "tipoCte" TEXT, "tipoFat" TEXT, "tipoFrete" TEXT,
                "tributaImpostos" TEXT, "ufCidCliente" TEXT, "ufCidDest" TEXT, "ufCidFil" TEXT, "ufCidRem" TEXT,
                "ufClientePrincipal" TEXT, "ufDest" TEXT, "ufOrig" TEXT, "vPercARet" REAL, "valorAbonoQuebra" REAL,
                "valorBalsa" REAL, "valorClassificacao" REAL, "valorEstadia" REAL, "valorFreteEmpresaICMS" REAL,
                "valorFreteFiscal" REAL, "valorICMS" REAL, "valorICMSNaoEmb" REAL, "valorINSS" REAL, "valorINSSEmpresa" REAL,
                "valorIRRF" REAL, "valorISS" REAL, "valorPedagio" REAL, "valorQuebra" REAL, "valorRastreamento" REAL,
                "valorSestSenat" REAL, "valorTotalDPsPagoViagem" REAL, "veiculoProprio" TEXT, "vlARec" REAL, "vlAfat" REAL,
                "vlCOFINS" REAL, "vlCSLL" REAL, "vlFaturado" REAL, "vlPIS" REAL, "vlRec" REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "relFilViagensCliente" (
                "acertoICMS" TEXT, "acertoSaldo" REAL, "adValor" REAL, "adiantamentoMotorista" REAL, "adtoMot2" REAL,
                "aliquotaCofins" REAL, "aliquotaIss" REAL, "aliquotaPis" REAL, "arqXMLAss" TEXT, "baseICMS" REAL,
                "baseICMSDireta" REAL, "baseImpostos" REAL, "baseIss" REAL, "cancelado" TEXT, "cargaDescarga" REAL,
                "cartaFrete" TEXT, "celularMotorista" TEXT, "celularProp" TEXT, "chaveNF" TEXT, "checkList" TEXT,
                "cidDestinoFormat" TEXT, "cidOrigemFormat" TEXT, "cnhMotorista" TEXT, "cnpjCpfCliente" TEXT,
                "cnpjCpfDest" TEXT, "cnpjCpfEmpresas" TEXT, "cnpjCpfFilial" TEXT, "cnpjCpfProp" TEXT, "cnpjCpfRemet" TEXT,
                "cnpjUnidadeEmb" TEXT, "codClDest" INTEGER, "codClRemet" INTEGER, "codCliente" INTEGER,
                "codColetaEntregaAg" INTEGER, "codEmpresas" INTEGER, "codFaturaSaldo" INTEGER, "codFilial" INTEGER,
                "codMercadoria" INTEGER, "codOrdemCar" INTEGER, "codProp" INTEGER, "codRota" INTEGER, "codServicoNfs" INTEGER,
                "codUnidadeEmb" INTEGER, "comissao" REAL, "cpfMotorista" TEXT, "cteChave" TEXT, "cteDataReciboEnv" TEXT,
                "cteFusoHorarioAutor" TEXT, "cteProt" TEXT, "cteStatus" TEXT, "dataALT" TEXT, "dataEmissao" TEXT,
                "dataEmissaoComHora" TEXT, "dataINS" TEXT, "dataNascimentoProp" TEXT, "dataPrevDescarga" TEXT,
                "dataPrevEntrega" TEXT, "dataViagemMotorista" TEXT, "descAg" TEXT, "descEntrega" TEXT, "descTipoCte" TEXT,
                "descontaICMSSaldoEmpresa" TEXT, "descontaINSSSaldoMot" TEXT, "descricaoEspecieMerc" TEXT,
                "descricaoMercadoria" TEXT, "despesaExtra" REAL, "despesasadicionais" REAL, "embarcadorNome" TEXT,
                "envioLote" TEXT, "estadiaEmbutidaFrete" TEXT, "fTotalPrest" REAL, "faturaICMSFinal" REAL,
                "faturaPesoChegada" REAL, "foneMotorista" TEXT, "foneProp" TEXT, "freteEmpresa" REAL, "freteEmpresaSai" REAL,
                "freteMotorista" REAL, "freteMotoristaSai" REAL, "fretePago" TEXT, "horaFimDescarga" TEXT, "icmsEmbutido" TEXT,
                "inscricaoEstadualFilial" TEXT, "margemFrete" REAL, "margemFretePerc" REAL, "modelo" TEXT, "natureza" TEXT,
                "nfseProt" TEXT, "nfseStatus" TEXT, "nfseStatusDesc" TEXT, "nomeCidCliente" TEXT, "nomeCidDestino" TEXT,
                "nomeCidOrigem" TEXT, "nomeClDest" TEXT, "nomeClRemet" TEXT, "nomeCliente" TEXT, "nomeEmpresas" TEXT,
                "nomeFilial" TEXT, "nomeMotorista" TEXT, "nomeProp" TEXT, "nomeUnidEmb" TEXT, "numConhec" INTEGER,
                "numConhecColEntrega" TEXT, "numNF" TEXT, "numNotaNF" TEXT, "numPedido" TEXT, "numero" TEXT,
                "numeroApolice" TEXT, "numeroColEntrega" TEXT, "obs" TEXT, "obsFaturaPeso" TEXT, "obsFiscal" TEXT,
                "outrosDescontos" REAL, "outrosDescontosMot" REAL, "outrosDescontosMot2" REAL, "pagaICMS" TEXT,
                "pagaISS" TEXT, "pagar" TEXT, "pedagioEmbFreteMot" TEXT, "pedagioEmbutido" TEXT, "pedagioEmbutidoFrete" TEXT,
                "pedidoCliente2" TEXT, "pedidoFrete" TEXT, "pedidoTransf" TEXT, "percRedVLICMS" REAL, "permiteFaturar" TEXT,
                "permitePagarSaldoFrota" TEXT, "pesoChegada" REAL, "pesoSaida" REAL, "pesoSaidaMotorista" REAL,
                "pisProp" TEXT, "placaVeiculo" TEXT, "porcICMS" REAL, "precoKgMercQuebra" REAL, "precoMercadoria" REAL,
                "precoTonEmpresa" REAL, "precoTonFiscal" REAL, "precoTonMotorista" REAL, "premioSeguro" REAL,
                "premioSeguro2" REAL, "quantMercadoria" REAL, "quantidadeQuebra" REAL, "quebraSegurada" TEXT,
                "quebraTotal" REAL, "rgMotorista" TEXT, "sacaCarRPapel" TEXT, "saldoMotorista" REAL,
                "secCatEmbutidoFrete" TEXT, "serieCte" TEXT, "serieNF" TEXT, "taxaQuebra" REAL, "tempo" TEXT, "tempoAtraso" TEXT,
                "tempoPrev" TEXT, "tempoTransp" TEXT, "tipoDesconto" TEXT, "tipoFrete" TEXT, "tipoTolerancia" TEXT,
                "tipoTributacao" TEXT, "toleranciaPesoCheg" REAL, "tributaImpostos" TEXT, "ufCliente" TEXT, "ufDestino" TEXT,
                "ufOrigem" TEXT, "usuarioALT" TEXT, "usuarioINS" TEXT, "valorAbonoQuebra" REAL, "valorBalsa" REAL,
                "valorClassificacao" REAL, "valorCofins" REAL, "valorEstadia" REAL, "valorFreteFiscal" REAL,
                "valorICMS" REAL, "valorINSS" REAL, "valorIRRF" REAL, "valorIss" REAL, "valorMercadoria" REAL,
                "valorPedagio" REAL, "valorPis" REAL, "valorQuebra" REAL, "valorSeguro" REAL, "valorSeguro2" REAL,
                "valorSestSenat" REAL, "valorTotalnf" REAL, "versaoCte" TEXT, "vlTotalPrestacaoDacte" REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "relFilDespesasGerais" (
                "VED" TEXT, "afaturar" TEXT, "agencia" TEXT, "ano" TEXT, "anoMes" TEXT, "banco" TEXT, "box" TEXT, "cadNota" TEXT,
                "cavalo" TEXT, "cep" TEXT, "chaveNfe" TEXT, "cidadeEmpresas" TEXT, "cidadeFilial" TEXT,
                "cidadeForn" TEXT, "cnpjCpf" TEXT, "cnpjCpfEmpresas" TEXT, "cnpjCpfFil" TEXT,
                "cnpjCpfFilial" TEXT, "cnpjCpfForn" TEXT, "codAcertoMotorista" INTEGER, "codAcertoProprietario" INTEGER,
                "codAdiantamento" INTEGER, "codAgrupador" INTEGER, "codCavalo" INTEGER, "codCfop" INTEGER,
                "codCfopItem" INTEGER, "codCliente" INTEGER, "codContaContabil" INTEGER, "codEmonitor" INTEGER,
                "codEmpresas" INTEGER, "codFatura" INTEGER, "codFaturaReceber" INTEGER, "codFilial" INTEGER,
                "codForn" INTEGER, "codFornProp" INTEGER, "codGrupoD" INTEGER, "codIBGECidC" INTEGER,
                "codIBGECidF" INTEGER, "codItemD" INTEGER, "codItemDServico" INTEGER, "codItemNota" INTEGER,
                "codMotNota" INTEGER, "codMotorista" INTEGER, "codNegocio" INTEGER, "codNota" INTEGER,
                "codProprietario" INTEGER, "codSituacao" INTEGER, "codSuperGrupoD" INTEGER, "codUeItem" INTEGER,
                "codUnidadeEmbarque" INTEGER, "codVeiculo" INTEGER, "conta" TEXT, "contaContabil" TEXT,
                "contrato" TEXT, "creditaPisCofins" TEXT, "creditaPisCofinsItem" TEXT, "cstCOFINSItem" TEXT,
                "cstCOFINSItemD" TEXT, "cstICMSItemD" TEXT, "cstIcmsItem" TEXT, "cstPISItem" TEXT,
                "cstPISItemD" TEXT, "custo" REAL, "custoTotal" REAL, "dataAcertoProp" TEXT, "dataControle" TEXT,
                "dataControleFormat" TEXT, "dataEmissao" TEXT, "dataFim" TEXT, "dataFimOficina" TEXT,
                "dataINS" TEXT, "dataIniOficina" TEXT, "dataMotorista" TEXT, "dataVenc" TEXT,
                "dataVencimento" TEXT, "descCodFilial" TEXT, "descCodForn" TEXT, "descCodGrupoDItemNota" TEXT,
                "descCodItemDItemNota" TEXT, "descCodSuperGrupoDItemNota" TEXT, "descCodUnidadeEmbarque" TEXT,
                "descGrupoD" TEXT, "descItemD" TEXT, "descNegocio" TEXT, "descSuperGrupoD" TEXT, "descUeItem" TEXT,
                "descUnidadeEmbarque" TEXT, "desconto" REAL, "despesa" TEXT, "endereco" TEXT, "especie" TEXT,
                "fontCenter" TEXT, "fontLeft" TEXT, "fontRight" TEXT, "frota" TEXT, "garantia" TEXT,
                "gerenciaEstoque" TEXT, "historico" TEXT, "id" INTEGER, "incluiRateio" TEXT, "inic" TEXT,
                "inscEst" TEXT, "inscEstForn" TEXT, "investimento" TEXT, "km" REAL, "kmAnterior" REAL,
                "kmPrev" REAL, "kmRodado" REAL, "kmRodadoDec" REAL, "liquido" REAL, "listItensDespesas" TEXT,
                "marcaAux" TEXT, "marcaVeic" TEXT, "mediaDesejada" REAL, "mediaInversa" REAL, "mediaKm" REAL,
                "mediaMax" REAL, "mediaMin" REAL, "modeloAux" TEXT, "modeloVeic" TEXT, "naoEncheuTanque" TEXT,
                "naoPrevista" TEXT, "ncmItemD" TEXT, "nfFatura" TEXT, "nfeDataHoraRecLote" TEXT, "nome" TEXT,
                "nomeCidC" TEXT, "nomeCidF" TEXT, "nomeCidFil" TEXT, "nomeEmpresas" TEXT, "nomeFil" TEXT,
                "nomeFilial" TEXT, "nomeForn" TEXT, "nomeMotorista" TEXT, "numNota" TEXT, "numeroNf" TEXT,
                "obs" TEXT, "obsItem" TEXT, "obsNota" TEXT, "orderFieldVeiculo" TEXT, "parcela" TEXT,
                "parcelas" TEXT, "placaCavalo" TEXT, "placaVeiculo" TEXT, "porcAliqIcmsSubsTribItem" REAL,
                "porcIcmsItem" REAL, "porcIpiItem" REAL, "quantidade" REAL, "rateioVeicProp" TEXT,
                "resumido" TEXT, "serie" TEXT, "serieNf" TEXT, "tempoPrevisto" REAL, "tipo" TEXT,
                "tipoConta" TEXT, "tipoNfe" TEXT, "tipoVeiculo" TEXT, "titular" TEXT, "ufCidC" TEXT,
                "ufCidF" TEXT, "ufCidFil" TEXT, "ufEmpresas" TEXT, "ufFilial" TEXT, "ufForn" TEXT,
                "unidade" TEXT, "usuarioAut" TEXT, "usuarioINS" TEXT, "valor" REAL, "valorAcertoProp" REAL,
                "valorBaseIcmsItem" REAL, "valorBaseIpiItem" REAL, "valorBaseSubsTribItem" REAL,
                "valorDescontoItem" REAL, "valorDespesa" REAL, "valorFaturamento" REAL, "valorFrete" REAL,
                "valorFreteEmp" REAL, "valorFreteMot" REAL, "valorIcmsItem" REAL, "valorImpSfed" REAL,
                "valorIpiItem" REAL, "valorIss" REAL, "valorItem" REAL, "valorMargem" REAL, "valorNota" REAL,
                "valorOutras" REAL, "valorPesoSaidaTon" REAL, "valorProd" REAL, "valorReceitaOp" REAL,
                "valorResultado" REAL, "valorResultadoComInv" REAL, "valorSeguro" REAL, "valorServ" REAL,
                "valorSubsTribItem" REAL, "valorUnit" REAL, "valorVenc" REAL, "veiculoProprio" TEXT,
                "vlBaseIcms" REAL, "vlBaseIcmsSubstTrib" REAL, "vlCofinsRet" REAL, "vlContabil" REAL,
                "vlCreditoIcms" REAL, "vlCsllRet" REAL, "vlIcms" REAL, "vlIcmsSubstTrib" REAL,
                "vlInssRet" REAL, "vlIpi" REAL, "vlIrrfRet" REAL, "vlPisRet" REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "relFilContasReceber" (
                "chaveJurosDescontos" TEXT, "cidCliente" TEXT, "cidFilial" TEXT, "codAcertoProprietario" INTEGER,
                "codBaixa" INTEGER, "codCliente" INTEGER, "codDuplicataReceber" INTEGER, "codEmpresas" INTEGER,
                "codFatura" INTEGER, "codFilial" INTEGER, "codTransacao" TEXT, "dataEmissao" TEXT, "dataPagto" TEXT,
                "dataVenc" TEXT, "descItemReceita" TEXT, "descNegocio" TEXT, "emailCliente" TEXT, "historico" TEXT,
                "historico1" TEXT, "historico2" TEXT, "jd" TEXT, "listConhecimentos" TEXT, "listDataEmissaoConhecimentos" TEXT,
                "listNotas" TEXT, "listaTiposFrete" TEXT, "nomeCliente" TEXT, "nomeEmpresas" TEXT, "nomeFilial" TEXT,
                "nomeFunc" TEXT, "numContabil" INTEGER, "numeroConta" TEXT, "numeroContaFatura" TEXT, "obs" TEXT,
                "obsTransacao" TEXT, "parcela" TEXT, "tipoFatura" TEXT, "ufCliente" TEXT, "ufFilial" TEXT,
                "valorPagto" REAL, "valorVenc" REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "relFilContasPagarDet" (
                "VED" TEXT, "agencia" TEXT, "banco" TEXT, "chaveJurosDescontos" TEXT, "chavePix" TEXT,
                "cidFilial" TEXT, "cidForn" TEXT, "cnpjCpfForn" TEXT, "codAcertoProprietario" INTEGER,
                "codBaixa" INTEGER, "codCheque" TEXT, "codDuplicataPagar" INTEGER, "codEmpresas" INTEGER,
                "codErpExterno" TEXT, "codFilial" INTEGER, "codForn" INTEGER, "codItemNota" INTEGER,
                "codNota" INTEGER, "codTipoPagto" INTEGER, "codTransacao" TEXT, "codUnidadeEmbarque" TEXT,
                "contaForn" TEXT, "dataEmissao" TEXT, "dataLib" TEXT, "dataPagto" TEXT,
                "dataPagtoFormat" TEXT, "dataPrevista" TEXT, "dataVenc" TEXT, "descGrupoD" TEXT,
                "descItemD" TEXT, "descTipoPagto" TEXT, "descUnidadeEmbarque" TEXT, "idTransacaoFretebras" TEXT,
                "jd" TEXT, "kmItemNota" REAL, "liquidoItemNota" REAL, "nomeEmpresas" TEXT,
                "nomeFilial" TEXT, "nomeForn" TEXT, "numConhec" INTEGER, "numNota" TEXT,
                "numeroConta" TEXT, "numeroContaParcela" TEXT, "obs" TEXT, "obsFaturaCompra" TEXT,
                "obsTransacao" TEXT, "parcela" TEXT, "pesoSaidaMotorista" REAL, "placaVeiculo" TEXT,
                "premioSeguro" REAL, "quantidadeItemNota" REAL, "serie" TEXT, "superGrupoD" TEXT,
                "totalTipoPagto" REAL, "ufFilial" TEXT, "ufForn" TEXT, "usuarioINS" TEXT,
                "usuarioLib" TEXT, "valorIcmsNota" REAL, "valorImpSfedNota" REAL, "valorIssNota" REAL,
                "valorNota" REAL, "valorPagto" REAL, "valorProporcional" REAL, "valorQuebra" REAL,
                "valorVenc" REAL, "vlCofinsRetNota" REAL, "vlCsllRetNota" REAL, "vlFat" REAL,
                "vlInssRetNota" REAL, "vlIrrfRetNota" REAL, "vlPisRetNota" REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "static_expense_groups" (
                "group_name" TEXT PRIMARY KEY,
                "is_despesa" TEXT DEFAULT 'S',
                "is_custo_viagem" TEXT DEFAULT 'N'
            )
        ''')
        
        is_sqlite = isinstance(conn, sqlite3.Connection)
        if is_sqlite:
            cursor.execute('INSERT OR IGNORE INTO "static_expense_groups" ("group_name") VALUES (?)', ('VALOR QUEBRA',))
            cursor.execute('INSERT OR IGNORE INTO "static_expense_groups" ("group_name", "is_despesa", "is_custo_viagem") VALUES (?, ?, ?)', ('COMISSÃO DE MOTORISTA', 'S', 'N'))
        else:
            cursor.execute('INSERT INTO "static_expense_groups" ("group_name") VALUES (%s) ON CONFLICT("group_name") DO NOTHING', ('VALOR QUEBRA',))
            cursor.execute('INSERT INTO "static_expense_groups" ("group_name", "is_despesa", "is_custo_viagem") VALUES (%s, %s, %s) ON CONFLICT("group_name") DO NOTHING', ('COMISSÃO DE MOTORISTA', 'S', 'N'))
    with get_db_connection() as conn:
        if conn is None:
            return
        cursor = conn.cursor()
        print("Verificando e criando esquema do banco de dados com nomes exatos...")

        # ... (código que cria as suas tabelas existentes, como relFilViagensFatCliente) ...
        
        # --- NOVO: Adiciona a tabela para as configurações do robô ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "configuracoes_robo" (
                "chave" TEXT PRIMARY KEY,
                "valor" TEXT
            )
        ''')
        conn.commit()
        print("Esquema do banco de dados verificado/criado com sucesso.")

def _clean_and_convert_data(df, table_key):
    original_columns = df.columns.tolist()
    df.columns = [str(col).strip() for col in original_columns]
    
    cleaned_columns_for_validation = df.columns.tolist()

    for col in df.select_dtypes(include=['object']).columns:
        if df[col].notna().any():
            df[col] = df[col].str.strip()
    
    col_maps = config.TABLE_COLUMN_MAPS.get(table_key, {})
    date_columns_to_process = col_maps.get('date_formats', {}).keys()
    for col_db in date_columns_to_process:
        if col_db in df.columns:
            df[col_db] = pd.to_datetime(df[col_db], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

    for col_type in ['numeric', 'integer']:
        for col_db in col_maps.get(col_type, []):
            if col_db in df.columns:
                df[col_db] = pd.to_numeric(df[col_db], errors='coerce').fillna(0)
                if col_type == 'integer':
                    df[col_db] = df[col_db].astype(int)

    return df, cleaned_columns_for_validation

def _validate_columns(excel_columns, table_name, conn):
    if conn is None: return excel_columns, []
    db_columns_case_sensitive = set()
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            db_columns_case_sensitive = {row['name'] for row in cursor.fetchall()}
        else: # PostgreSQL
            df_schema = pd.read_sql(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'", conn)
            db_columns_case_sensitive = set(df_schema['column_name'])
    except Exception as e:
        print(f"AVISO: Não foi possível ler colunas da tabela '{table_name}'. Erro: {e}")
        return excel_columns, []

    db_columns_lower = {col.lower() for col in db_columns_case_sensitive}
    extra_cols_names = [col for col in excel_columns if col.lower() not in db_columns_lower]
    valid_columns_original_case = [col for col in excel_columns if col.lower() in db_columns_lower]
    return valid_columns_original_case, extra_cols_names

def import_excel_to_db(excel_source, sheet_name: str, table_name: str):
    extra_columns = []
    try:
        df_novo = pd.read_excel(excel_source, sheet_name=sheet_name)
        df_novo, cleaned_excel_columns = _clean_and_convert_data(df_novo, table_name)
        
        with get_db_connection() as conn:
            valid_columns, extra_columns = _validate_columns(cleaned_excel_columns, table_name, conn)
            
            df_import = df_novo[[col for col in df_novo.columns if col in valid_columns]]
            
            if conn is None: return extra_columns

            cursor = conn.cursor()
            delete_sql = f'DELETE FROM "{table_name}"'
            print(f"Limpando dados antigos da tabela '{table_name}'...")
            cursor.execute(delete_sql)
            
            print(f"Inserindo {len(df_import)} novos registros em '{table_name}'...")
            df_import.to_sql(table_name, conn, if_exists='append', index=False)
            conn.commit()
            print(f"Dados da planilha '{sheet_name}' importados para a tabela '{table_name}'.")

        return extra_columns
    except Exception as e:
        print(f"Erro ao importar dados da planilha '{sheet_name}' para '{table_name}': {e}")
        raise e

def import_single_excel_to_db(excel_source, file_key: str):
    file_info = config.EXCEL_FILES_CONFIG.get(file_key)
    if not file_info:
        raise ValueError(f"Chave de arquivo '{file_key}' não encontrada na configuração.")
    return import_excel_to_db(excel_source, file_info["sheet_name"], file_info["table_name"])

def table_exists(table_name: str) -> bool:
    """Verifica se uma tabela existe no banco de dados."""
    try:
        with get_db_connection() as conn:
            if conn is None: return False
            query_check_table = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'" if isinstance(conn, sqlite3.Connection) else f"SELECT to_regclass('{table_name}')"
            cursor = conn.cursor()
            cursor.execute(query_check_table)
            result = cursor.fetchone()
            return result is not None and result[0] is not None
    except Exception:
        return False
    


def processar_downloads_na_pasta():
    """
    Verifica a pasta do projeto por planilhas baixadas, importa-as,
    renomeia com data/hora e limpa versões antigas.
    """
    print("\n--- INICIANDO PROCESSAMENTO PÓS-DOWNLOAD NA PASTA ---")
    caminho_base = os.getcwd()
    
    # Mapeia o nome de cada arquivo para a sua chave de configuração (ex: "relFil...xls": "contas_pagar")
    mapa_arquivos_config = {info['path']: chave for chave, info in config.EXCEL_FILES_CONFIG.items()}
    
    # Para cada tipo de relatório que conhecemos do config.py...
    for nome_arquivo_base, chave_config in mapa_arquivos_config.items():
        
        caminho_novo_arquivo = os.path.join(caminho_base, nome_arquivo_base)
        
        # 1. Verifica se o robô realmente baixou um novo arquivo deste tipo
        if os.path.exists(caminho_novo_arquivo):
            print(f"\nArquivo novo encontrado: '{nome_arquivo_base}'")

            # 2. Procura e exclui QUALQUER versão antiga e já renomeada deste mesmo relatório
            nome_sem_ext, extensao = os.path.splitext(nome_arquivo_base)
            padrao_busca_antigos = os.path.join(caminho_base, f"{nome_sem_ext}_*{extensao}")
            arquivos_antigos_encontrados = glob.glob(padrao_busca_antigos)
            
            if arquivos_antigos_encontrados:
                print(f" -> Excluindo {len(arquivos_antigos_encontrados)} versão(ões) antiga(s)...")
                for arquivo_antigo in arquivos_antigos_encontrados:
                    os.remove(arquivo_antigo)

            # 3. Importa os dados do novo arquivo para o banco de dados
            try:
                print(f" -> Importando dados para a tabela '{config.EXCEL_FILES_CONFIG[chave_config]['table_name']}'...")
                # Reutiliza a função de importação que já existe no seu projeto
                import_single_excel_to_db(caminho_novo_arquivo, chave_config)
                print(" -> Importação bem-sucedida.")
            except Exception as e:
                print(f" -> ERRO! Falha ao importar os dados: {e}")
                # Se a importação falhar, paramos o processo para este arquivo para evitar renomeá-lo incorretamente
                continue

            # 4. Renomeia o novo arquivo com data e hora para guardá-lo como "antigo"
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                novo_nome_renomeado = f"{nome_sem_ext}_{timestamp}{extensao}"
                caminho_renomeado = os.path.join(caminho_base, novo_nome_renomeado)
                print(f" -> Renomeando arquivo para '{novo_nome_renomeado}'...")
                os.rename(caminho_novo_arquivo, caminho_renomeado)
            except Exception as e:
                print(f" -> ERRO! Falha ao renomear o arquivo: {e}")

    print("\n--- PROCESSAMENTO PÓS-DOWNLOAD FINALIZADO ---")