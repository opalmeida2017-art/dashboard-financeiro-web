# database.py
import os
import psycopg2
import sqlite3
import pandas as pd
import config
from datetime import datetime

# CORREÇÃO AQUI: Definimos o nome do DB local diretamente.
DATABASE_NAME = 'financeiro.db'

# --- SUBSTITUA A FUNÇÃO ANTIGA POR ESTA ---
def get_db_connection():
    """
    Cria e retorna uma conexão com o banco de dados.
    Usa PostgreSQL se a variável de ambiente DATABASE_URL estiver definida (no Render).
    Caso contrário, usa o banco de dados SQLite local.
    """
    db_url = os.getenv('DATABASE_URL')
    
    if db_url:
        # Ambiente de produção (Render)
        try:
            print("Conectando ao banco de dados PostgreSQL...")
            conn = psycopg2.connect(db_url)
            # No psycopg2, o 'row_factory' é definido ao criar o cursor, não na conexão.
            # E para o Pandas, não é necessário.
            return conn
        except psycopg2.Error as e:
            print(f"Erro ao conectar ao PostgreSQL: {e}")
            return None
    else:
        # Ambiente local
        try:
            print("Conectando ao banco de dados SQLite local...")
            conn = sqlite3.connect(DATABASE_NAME)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            print(f"Erro ao conectar ao banco de dados SQLite: {e}")
            return None

# O resto do seu arquivo database.py (create_tables, etc.) pode continuar igual por enquanto.
# Apenas a função de conexão precisa mudar.

def create_tables():
    """
    Cria as tabelas do banco de dados com um esquema fixo.
    """
    with get_db_connection() as conn:
        if conn is None: return
        cursor = conn.cursor()

        # --- Tabela: relFilViagensCliente ---
        print("Verificando/Criando a tabela 'relFilViagensCliente'...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relFilViagensCliente (
                acertoICMS TEXT, acertoSaldo REAL, adValor REAL, adiantamentoMotorista REAL, adtoMot2 REAL,
                aliquotaCofins REAL, aliquotaIss REAL, aliquotaPis REAL, arqXMLAss TEXT, baseICMS REAL,
                baseICMSDireta REAL, baseImpostos REAL, baseIss REAL, cancelado TEXT, cargaDescarga REAL,
                cartaFrete TEXT, celularMotorista TEXT, celularProp TEXT, chaveNF TEXT, checkList TEXT,
                cidDestinoFormat TEXT, cidOrigemFormat TEXT, cnhMotorista TEXT, cnpjCpfCliente TEXT,
                cnpjCpfDest TEXT, cnpjCpfEmpresas TEXT, cnpjCpfFilial TEXT, cnpjCpfProp TEXT,
                cnpjCpfRemet TEXT, cnpjUnidadeEmb TEXT, codClDest INTEGER, codClRemet INTEGER,
                codCliente INTEGER, codColetaEntregaAg INTEGER, codEmpresas INTEGER, codFaturaSaldo INTEGER,
                codFilial INTEGER, codMercadoria INTEGER, codOrdemCar INTEGER, codProp INTEGER, codRota INTEGER,
                codServicoNfs INTEGER, codUnidadeEmb INTEGER, comissao REAL, cpfMotorista TEXT,
                cteChave TEXT, cteDataReciboEnv TEXT, cteFusoHorarioAutor TEXT, cteProt TEXT, cteStatus TEXT,
                dataALT TEXT, dataEmissao TEXT, dataEmissaoComHora TEXT, dataINS TEXT, dataNascimentoProp TEXT,
                dataPrevDescarga TEXT, dataPrevEntrega TEXT, dataViagemMotorista TEXT, descAg TEXT,
                descEntrega TEXT, descTipoCte TEXT, descontaICMSSaldoEmpresa TEXT, descontaINSSSaldoMot TEXT,
                descricaoEspecieMerc TEXT, descricaoMercadoria TEXT, despesaExtra REAL,
                despesasadicionais REAL, embarcadorNome TEXT, envioLote TEXT, estadiaEmbutidaFrete TEXT,
                fTotalPrest REAL, faturaICMSFinal REAL, faturaPesoChegada REAL, foneMotorista TEXT,
                foneProp TEXT, freteEmpresa REAL, freteEmpresaSai REAL, freteMotorista REAL,
                freteMotoristaSai REAL, fretePago TEXT, 
                
                horaFimDescarga TEXT, -- << AJUSTE: Corrigido erro de digitação aqui

                icmsEmbutido TEXT, inscricaoEstadualFilial TEXT, margemFrete REAL, margemFretePerc REAL, modelo TEXT,
                natureza TEXT, nfseProt TEXT, nfseStatus TEXT, nfseStatusDesc TEXT, nomeCidCliente TEXT,
                nomeCidDestino TEXT, nomeCidOrigem TEXT, nomeClDest TEXT, nomeClRemet TEXT, nomeCliente TEXT,
                nomeEmpresas TEXT, nomeFilial TEXT, nomeMotorista TEXT, nomeProp TEXT, nomeUnidEmb TEXT,
                numConhec INTEGER, numConhecColEntrega TEXT, numNF TEXT, numNotaNF TEXT, numPedido TEXT,
                numero TEXT, numeroApolice TEXT, numeroColEntrega TEXT, obs TEXT, obsFaturaPeso TEXT,
                obsFiscal TEXT, outrosDescontos REAL, outrosDescontosMot REAL, outrosDescontosMot2 REAL,
                pagaICMS TEXT, pagaISS TEXT, pagar TEXT, pedagioEmbFreteMot TEXT, pedagioEmbutido TEXT,
                pedagioEmbutidoFrete TEXT, pedidoCliente2 TEXT, pedidoFrete TEXT, pedidoTransf TEXT,
                percRedVLICMS REAL, permiteFaturar TEXT, permitePagarSaldoFrota TEXT, pesoChegada REAL,
                pesoSaida REAL, pesoSaidaMotorista REAL, pisProp TEXT, placaVeiculo TEXT, porcICMS REAL,
                precoKgMercQuebra REAL, precoMercadoria REAL, precoTonEmpresa REAL, precoTonFiscal REAL,
                precoTonMotorista REAL, premioSeguro REAL, premioSeguro2 REAL, quantMercadoria REAL,
                quantidadeQuebra REAL, quebraSegurada TEXT, quebraTotal REAL, rgMotorista TEXT,
                sacaCarRPapel TEXT, saldoMotorista REAL, secCatEmbutidoFrete TEXT, serieCte TEXT,
                serieNF TEXT, taxaQuebra REAL, tempo TEXT, tempoAtraso TEXT, tempoPrev TEXT, tempoTransp TEXT,
                tipoDesconto TEXT, tipoFrete TEXT, tipoTolerancia TEXT, tipoTributacao TEXT,
                toleranciaPesoCheg REAL, tributaImpostos TEXT, ufCliente TEXT, ufDestino TEXT, ufOrigem TEXT,
                usuarioALT TEXT, usuarioINS TEXT, valorAbonoQuebra REAL, valorBalsa REAL,
                valorClassificacao REAL, valorCofins REAL, valorEstadia REAL, valorFreteFiscal REAL,
                valorICMS REAL, valorINSS REAL, valorIRRF REAL, valorIss REAL, valorMercadoria REAL,
                valorPedagio REAL, valorPis REAL, valorQuebra REAL, valorSeguro REAL, valorSeguro2 REAL,
                valorSestSenat REAL, valorTotalnf REAL, versaoCte TEXT, vlTotalPrestacaoDacte REAL
            )
        ''')

        # --- Tabela: relFilViagensFatCliente ---
        print("Verificando/Criando a tabela 'relFilViagensFatCliente'...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relFilViagensFatCliente (
                COFINS REAL, CSLL REAL, PIS REAL, acertoSaldo REAL, adiantamentoEmp2 REAL,
                adiantamentoEmpresa REAL, adiantamentoMotorista REAL, adtoMot2 REAL, agregado TEXT,
                baseISS REAL, cargaDescarga REAL, cepCliente TEXT, cidCliente TEXT, cidDest TEXT,
                cidEmpresas TEXT, cidOrig TEXT, cidadeClientePrincipal TEXT, cidadeDest TEXT,
                cidadeFil TEXT, cidadeRem TEXT, classificacaoEmbFreteEmp TEXT, clientePagaSaldoMotorista TEXT,
                cnpjCpfCliente TEXT, cnpjCpfEmpresas TEXT, cnpjCpfFil TEXT, cnpjCpfProp TEXT,
                codAcertoProprietario INTEGER, codCheque TEXT, codCliente INTEGER, codClientePrincipal INTEGER,
                codDest INTEGER, codFatPagAdiant INTEGER, codFatPagSaldo INTEGER, codFaturaAdiantEmp2 INTEGER,
                codFaturaAdiantamento INTEGER, codFaturaClassificacao INTEGER, codFaturaEstadia INTEGER,
                codFaturaICMS INTEGER, codFaturaPedagio INTEGER, codFaturaSaldo INTEGER, codFaturaSaldoComp INTEGER,
                codFilial INTEGER, codFornecedorAdiant INTEGER, codFornecedorClassificacao INTEGER,
                codFornecedorICMS INTEGER, codFornecedorPedagio INTEGER, codFornecedorSaldo INTEGER,
                codManif INTEGER, codMercadoria INTEGER, codProp INTEGER, codRem INTEGER, codTipoCliente INTEGER,
                codTransAdiant INTEGER, codTransEstadia INTEGER, codTransICMS INTEGER, codTransPedagio INTEGER,
                codTransSaldo INTEGER, codVeiculo INTEGER, complementoCliente TEXT, contrato TEXT, cpfMot TEXT,
                cteDataReciboEnv TEXT, cteStatus TEXT, cteStatusDesc TEXT, dataChegouSaldo TEXT,
                dataEmissao TEXT, dataEncerramento TEXT, dataFatPagAdiant TEXT, dataFatPagSaldo TEXT,
                dataINS TEXT, dataNascimentoMot TEXT, dataPagtoDuplicatas TEXT, dataPrevDescarga TEXT,
                dataVencAdiant TEXT, dataVencSaldo TEXT, dataViagemMotorista TEXT,
                descCSLLSaldoEmp REAL, descCofinsSaldoEmp REAL, descColeta REAL, descDifFrete REAL,
                descEntrega REAL, descIRRFSaldoEmp REAL, descPISSaldoEmp REAL, descPedagioBaseMot REAL,
                descQuebraSaldoEmp TEXT, descSeguro2Saldo REAL, descSeguro2SaldoMot REAL,
                descSeguroSaldo REAL, descSeguroSaldoMot REAL, descSestSenatSaldoEmp REAL,
                descontaICMSSaldoEmpresa TEXT, descontaINSSSaldo TEXT, descontaINSSSaldoMot TEXT,
                descontaISSSaldoEmp TEXT, descricaoMercadoria TEXT, despesaExtra REAL, enderecoCliente TEXT,
                enderecoEmpresas TEXT, enderecoFil TEXT, estadiaEmbutidaFrete TEXT, fEmp REAL,
                faturaICMSFinal REAL, faturaPesoChegada REAL, faturamento REAL, faxEmpresas TEXT,
                faxFil TEXT, foneCliente TEXT, foneEmpresas TEXT, foneFil TEXT, freteCombinado REAL,
                freteEmpresa REAL, freteEmpresaComp REAL, freteEmpresaSai REAL, freteMotorista REAL,
                freteMotoristaSai REAL, historico1FatSaldo TEXT, historico2FatSaldo TEXT, historicoFatSaldo TEXT,
                horaFimDescarga TEXT, icmsEmbutido TEXT, inscEstCliente TEXT, issEmbutido TEXT,
                kmFim REAL, kmIni REAL, kmParc REAL, kmRodado REAL, liberadoOrdServ TEXT, nomeCliente TEXT,
                nomeClientePrincipal TEXT, nomeDest TEXT, nomeEmpresas TEXT, nomeFilial TEXT,
                nomeFornSaldo TEXT, nomeMot TEXT, nomeProp TEXT, nomeRem TEXT, numConhec INTEGER,
                numNF TEXT, numPedido TEXT, numero TEXT, numeroClassificacao TEXT, numeroICMS TEXT,
                numeroProgramacao TEXT, obsFatSaldo TEXT, outrosDescontos REAL, outrosDescontosMot REAL,
                outrosDescontosMot2 REAL, pagaICMS TEXT, pedagioEmbutidoFrete TEXT, pedidoFrete TEXT,
                percRedVLICMS REAL, permiteFaturar TEXT, permitePagarSaldoFrota TEXT, pesoChegada REAL,
                pesoSaida REAL, pesoSaidaMotorista REAL, placa TEXT, precoTonEmpresa REAL,
                precoTonMotorista REAL, premioSeguro REAL, premioSeguro2 REAL, quantMercadoria REAL,
                quantidadeQuebra REAL, quebraSegurada TEXT, saldoEmp REAL, saldoMotorista REAL,
                somaFreteEmpresaComICMS REAL, somarISSFatSaldo TEXT, taxaAdiantEmpresa REAL,
                tipoCte TEXT, tipoFat TEXT, tipoFrete TEXT, tributaImpostos TEXT, ufCidCliente TEXT,
                ufCidDest TEXT, ufCidFil TEXT, ufCidRem TEXT, ufClientePrincipal TEXT, ufDest TEXT,
                ufOrig TEXT, vPercARet REAL, valorAbonoQuebra REAL, valorBalsa REAL, valorClassificacao REAL,
                valorEstadia REAL, valorFreteEmpresaICMS REAL, valorFreteFiscal REAL, valorICMS REAL,
                valorICMSNaoEmb REAL, valorINSS REAL, valorINSSEmpresa REAL, valorIRRF REAL,
                valorISS REAL, valorPedagio REAL, valorQuebra REAL, valorRastreamento REAL,
                valorSestSenat REAL, valorTotalDPsPagoViagem REAL, veiculoProprio TEXT, vlARec REAL,
                vlAfat REAL, vlCOFINS REAL, vlCSLL REAL, vlFaturado REAL, vlPIS REAL, vlRec REAL,
                placaVeiculo TEXT, custoTotal REAL
            )
        ''')

        # --- Tabela: relFilDespesasGerais ---
        print("Verificando/Criando a tabela 'relFilDespesasGerais'...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relFilDespesasGerais (
                afaturar TEXT, agencia TEXT, ano TEXT, anoMes TEXT, banco TEXT, box TEXT, cadNota TEXT,
                cavalo TEXT, cep TEXT, chaveNfe TEXT, cidadeEmpresas TEXT, cidadeFilial TEXT,
                cidadeForn TEXT, cnpjCpf TEXT, cnpjCpfEmpresas TEXT, cnpjCpfFil TEXT,
                cnpjCpfFilial TEXT, cnpjCpfForn TEXT, codAcertoMotorista INTEGER,
                codAcertoProprietario INTEGER, codAdiantamento INTEGER, codAgrupador INTEGER,
                codCavalo INTEGER, codCfop INTEGER, codCfopItem INTEGER, codCliente INTEGER,
                codContaContabil INTEGER, codEmonitor INTEGER, codEmpresas INTEGER, codFatura INTEGER,
                codFaturaReceber INTEGER, codFilial INTEGER, codForn INTEGER, codFornProp INTEGER,
                codGrupoD INTEGER, codIBGECidC INTEGER, codIBGECidF INTEGER, codItemD INTEGER,
                codItemDServico INTEGER, codItemNota INTEGER, codMotNota INTEGER, codMotorista INTEGER,
                codNegocio INTEGER, codNota INTEGER, codProprietario INTEGER, codSituacao INTEGER,
                codSuperGrupoD INTEGER, codUeItem INTEGER, codUnidadeEmbarque INTEGER, codVeiculo INTEGER,
                conta TEXT, contaContabil TEXT, contrato TEXT, creditaPisCofins TEXT,
                creditaPisCofinsItem TEXT, cstCOFINSItem TEXT, cstCOFINSItemD TEXT, cstICMSItemD TEXT,
                cstIcmsItem TEXT, cstPISItem TEXT, cstPISItemD TEXT, custo REAL, custoTotal REAL,
                dataAcertoProp TEXT, dataControle TEXT, dataControleFormat TEXT, dataEmissao TEXT,
                dataFim TEXT, dataFimOficina TEXT, dataINS TEXT, dataIniOficina TEXT, dataMotorista TEXT,
                dataVenc TEXT, dataVencimento TEXT, descCodFilial TEXT, descCodForn TEXT,
                descCodGrupoDItemNota TEXT, descCodItemDItemNota TEXT, descCodSuperGrupoDItemNota TEXT,
                descCodUnidadeEmbarque TEXT, descGrupoD TEXT, descItemD TEXT, descNegocio TEXT,
                descSuperGrupoD TEXT, descUeItem TEXT, descUnidadeEmbarque TEXT, desconto REAL,
                despesa TEXT, endereco TEXT, especie TEXT, fontCenter TEXT, fontLeft TEXT, fontRight TEXT,
                frota TEXT, garantia TEXT, gerenciaEstoque TEXT, historico TEXT, id INTEGER,
                incluiRateio TEXT, inic TEXT, inscEst TEXT, inscEstForn TEXT, investimento TEXT, km REAL,
                kmAnterior REAL, kmPrev REAL, kmRodado REAL, kmRodadoDec REAL, liquido REAL,
                listItensDespesas TEXT, marcaAux TEXT, marcaVeic TEXT, mediaDesejada REAL,
                mediaInversa REAL, mediaKm REAL, mediaMax REAL, mediaMin REAL, modeloAux TEXT,
                modeloVeic TEXT, naoEncheuTanque TEXT, naoPrevista TEXT, ncmItemD TEXT, nfFatura TEXT,
                nfeDataHoraRecLote TEXT, nome TEXT, nomeCidC TEXT, nomeCidF TEXT, nomeCidFil TEXT,
                nomeEmpresas TEXT, nomeFil TEXT, nomeFilial TEXT, nomeForn TEXT, nomeMotorista TEXT,
                numNota TEXT, numeroNf TEXT, obs TEXT, obsItem TEXT, obsNota TEXT,
                orderFieldVeiculo TEXT, parcela TEXT, parcelas TEXT, placaCavalo TEXT,
                placaVeiculo TEXT, porcAliqIcmsSubsTribItem REAL, porcIcmsItem REAL, porcIpiItem REAL,
                quantidade REAL, rateioVeicProp TEXT, resumido TEXT, serie TEXT, serieNf TEXT,
                tempoPrevisto REAL, tipo TEXT, tipoConta TEXT, tipoNfe TEXT, tipoVeiculo TEXT,
                titular TEXT, ufCidC TEXT, ufCidF TEXT, ufCidFil TEXT, ufEmpresas TEXT, ufFilial TEXT,
                ufForn TEXT, unidade TEXT, usuarioAut TEXT, usuarioINS TEXT, valor REAL,
                valorAcertoProp REAL, valorBaseIcmsItem REAL, valorBaseIpiItem REAL,
                valorBaseSubsTribItem REAL, valorDescontoItem REAL, valorDespesa REAL,
                valorFaturamento REAL, valorFrete REAL, valorFreteEmp REAL, valorFreteMot REAL,
                valorIcmsItem REAL, valorImpSfed REAL, valorIpiItem REAL, valorIss REAL, valorItem REAL,
                valorMargem REAL, valorNota REAL, valorOutras REAL, valorPesoSaidaTon REAL,
                valorProd REAL, valorReceitaOp REAL, valorResultado REAL, valorResultadoComInv REAL,
                valorSeguro REAL, valorServ REAL, valorSubsTribItem REAL, valorUnit REAL, valorVenc REAL,
                veiculoProprio TEXT, vlBaseIcms REAL, vlBaseIcmsSubstTrib REAL, vlCofinsRet REAL,
                vlContabil REAL, vlCreditoIcms REAL, vlCsllRet REAL, vlIcms REAL,
                vlIcmsSubstTrib REAL, vlInssRet REAL, vlIpi REAL, vlIrrfRet REAL, vlPisRet REAL,
                VED TEXT, e_custo_viagem TEXT
            )
        ''')

        # --- Tabela: relFilContasPagarDet ---
        print("Verificando/Criando a tabela 'relFilContasPagarDet'...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relFilContasPagarDet (
                VED TEXT, codForn TEXT, codItemNota TEXT, codTransacao TEXT, codUnidadeEmbarque TEXT,
                dataEmissao TEXT, dataPagto TEXT, dataVenc TEXT, descGrupoD TEXT, descItemD TEXT,
                descUnidadeEmbarque TEXT, liquidoItemNota REAL, nomeFilial TEXT, nomeForn TEXT,
                numNota TEXT, parcela TEXT, placaVeiculo TEXT, quantidadeItemNota REAL, serie TEXT,
                superGrupoD TEXT, valorNota REAL, valorPagto REAL, valorVenc REAL,
                dataControle TEXT, pago TEXT
            )
        ''')

        # --- Tabela: relFilContasReceber ---
        print("Verificando/Criando a tabela 'relFilContasReceber'...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relFilContasReceber (
                chaveJurosDescontos TEXT, cidCliente TEXT, cidFilial TEXT, codAcertoProprietario INTEGER,
                codBaixa INTEGER, codCliente INTEGER, codDuplicataReceber INTEGER, codEmpresas INTEGER,
                codFatura INTEGER, codFilial INTEGER, codTransacao TEXT, dataEmissao TEXT,
                dataPagto TEXT, dataVenc TEXT, descItemReceita TEXT, descNegocio TEXT,
                emailCliente TEXT, historico TEXT, historico1 TEXT, historico2 TEXT, jd TEXT,
                listConhecimentos TEXT, listDataEmissaoConhecimentos TEXT, listNotas TEXT,
                listaTiposFrete TEXT, nomeCliente TEXT, nomeEmpresas TEXT, nomeFilial TEXT,
                nomeFunc TEXT, numContabil INTEGER, numeroConta TEXT, numeroContaFatura TEXT,
                obs TEXT, obsTransacao TEXT, parcela TEXT, tipoFatura TEXT, ufCliente TEXT,
                ufFilial TEXT, valorPagto REAL, valorVenc REAL,
                dataViagemMotorista TEXT, numConhec INTEGER, numNF TEXT, nomeFil TEXT, recebido TEXT
            )
        ''')

       
        # --- Tabela: static_expense_groups ---
        print("Verificando/Criando a tabela 'static_expense_groups'...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS static_expense_groups (
                group_name TEXT PRIMARY KEY,
                is_despesa TEXT DEFAULT 'S',
                is_custo_viagem TEXT DEFAULT 'N'
            )
        ''')

        # Insere valores padrão em static_expense_groups de forma compatível com SQLite e PostgreSQL
        db_type = type(conn).__module__
        if "sqlite3" in db_type:
            cursor.execute("INSERT OR IGNORE INTO static_expense_groups (group_name) VALUES ('VALOR QUEBRA')")
            cursor.execute("INSERT OR IGNORE INTO static_expense_groups (group_name, is_despesa, is_custo_viagem) VALUES ('COMISSÃO DE MOTORISTA', 'S', 'N')")
        else:
            cursor.execute("INSERT INTO static_expense_groups (group_name) VALUES ('VALOR QUEBRA') ON CONFLICT DO NOTHING")
            cursor.execute("INSERT INTO static_expense_groups (group_name, is_despesa, is_custo_viagem) VALUES ('COMISSÃO DE MOTORISTA', 'S', 'N') ON CONFLICT DO NOTHING")
        
        # A linha com erro foi removida.

        conn.commit()
        print("\n--- Esquema completo do banco de dados verificado/criado com sucesso! ---")

def reset_all_tables():
    """Apaga todas as tabelas para uma reinicialização completa dos dados."""
    all_tables = [info["table_name"] for info in config.EXCEL_FILES_CONFIG.values()]
    unique_tables = list(set(all_tables))
    with get_db_connection() as conn:
        if conn is None: return
        cursor = conn.cursor()
        for table_name in unique_tables:
            try:
                print(f"Apagando a tabela: {table_name}...")
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            except (sqlite3.Error, psycopg2.Error, Exception) as e:
                print(f"Erro ao apagar a tabela {table_name}: {e}")
        conn.commit()
        create_tables()
        print("Todas as tabelas foram recriadas com sucesso.")


# Em database.py, substitua apenas esta função:

def _clean_and_convert_data(df, table_key):
    """Limpa e converte os tipos de dados do DataFrame antes da importação."""
    print(f"\nLimpando e convertendo dados para a tabela: '{table_key}'")
    df.columns = [str(col).strip().replace(' ', '') for col in df.columns]
    
    if 'placa' in df.columns and 'placaVeiculo' not in df.columns:
        df.rename(columns={'placa': 'placaVeiculo'}, inplace=True)

    for col in df.select_dtypes(include=['object']).columns:
        if df[col].notna().any():
            df[col] = df[col].str.strip()
    
    # --- AJUSTE PRINCIPAL AQUI ---
    # Define o formato de data exato que vem da sua planilha
    date_format_from_excel = '%d/%m/%Y %H:%M:%S.%f'
    
    col_maps = config.TABLE_COLUMN_MAPS.get(table_key, {})
    # Usamos .keys() para pegar apenas a lista de nomes de colunas de data do config
    date_columns_to_process = col_maps.get('date_formats', {}).keys()

    for col_db in date_columns_to_process:
        if col_db in df.columns:
            print(f"  -> [DEBUG DATA] Processando coluna de data: '{col_db}' com formato explícito.")
            
            # Converte a coluna para o tipo data usando o formato exato
            # Isso é muito mais robusto do que tentar adivinhar o formato.
            df[col_db] = pd.to_datetime(df[col_db], format=date_format_from_excel, errors='coerce')
            
            # Conta quantas datas falharam na conversão
            invalid_dates = df[col_db].isna().sum()
            if invalid_dates > 0:
                print(f"    -> ALERTA: {invalid_dates} valores na coluna '{col_db}' não puderam ser convertidos e serão salvos como nulos.")

            # Converte de volta para texto no formato padrão do banco de dados (YYYY-MM-DD HH:MM:SS)
            df[col_db] = df[col_db].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else None)

    for col_type in ['numeric', 'integer']:
        for col_db in col_maps.get(col_type, []):
            if col_db in df.columns:
                df[col_db] = pd.to_numeric(df[col_db], errors='coerce').fillna(0)
                if col_type == 'integer':
                    df[col_db] = df[col_db].astype(int)
    return df


def _validate_columns(df_columns, table_name):
    """Valida as colunas da planilha contra as colunas da tabela do banco de dados."""
    print(f"\nValidando colunas da tabela '{table_name}'...")
    with get_db_connection() as conn:
        if conn is None:
            return
        cursor = conn.cursor()
        db_type = type(conn).__module__
        db_columns = set()
        try:
            if "sqlite3" in db_type:
                cursor.execute(f"PRAGMA table_info({table_name})")
                db_columns = {row['name'] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()}
            elif "psycopg2" in db_type:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = %s
                """, (table_name,))
                db_columns = {row[0] for row in cursor.fetchall()}
            else:
                print("Tipo de banco de dados não suportado para validação de colunas.")
                return list(df_columns)
        except Exception as e:
            print(f"Erro ao obter colunas da tabela '{table_name}': {e}")
            return list(df_columns)

    excel_cols_set = set(df_columns)

    extra_in_excel = excel_cols_set - db_columns
    if extra_in_excel:
        print(f"  -> AVISO: Colunas no Excel que não existem na tabela do banco: {sorted(list(extra_in_excel))}")
        print("     -> Essas colunas serão ignoradas na importação.")

    missing_in_excel = db_columns - excel_cols_set
    if missing_in_excel:
        print(f"  -> INFO: Colunas na tabela do banco que não foram encontradas no Excel: {sorted(list(missing_in_excel))}")

    print("Validação de colunas concluída.")
    return list(db_columns.intersection(excel_cols_set))


def import_excel_to_db(excel_path: str, sheet_name: str, table_name: str):
    """Importa dados de uma planilha Excel para a tabela correspondente no banco de dados."""
    try:
        df_novo = pd.read_excel(excel_path, sheet_name=sheet_name)
        df_novo = _clean_and_convert_data(df_novo, table_name)
        
        valid_columns = _validate_columns(df_novo.columns, table_name)
        df_import = df_novo[valid_columns]

        with get_db_connection() as conn:
            if conn is None: return
            cursor = conn.cursor()

            print(f"Limpando dados antigos da tabela '{table_name}'...")
            cursor.execute(f"DELETE FROM {table_name}")
            conn.commit()
            
            print(f"Inserindo {len(df_import)} novos registros em '{table_name}'...")
            df_import.to_sql(table_name, conn, if_exists='append', index=False)
            
            conn.commit()
            print(f"Dados da planilha '{sheet_name}' importados para a tabela '{table_name}'.")
            
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")
                base, ext = os.path.splitext(excel_path)
                new_path = f"{base}_importado_{timestamp}{ext}"
                os.rename(excel_path, new_path)
                print(f"Arquivo '{os.path.basename(excel_path)}' arquivado como '{os.path.basename(new_path)}'.")
            except OSError as e:
                print(f"AVISO: Não foi possível renomear o arquivo {excel_path}: {e}")

    except Exception as e:
        if "has no column named" in str(e):
            print(f"ERRO CRÍTICO: A estrutura da planilha mudou! {e}")
            print("Verifique se o arquivo Excel tem as mesmas colunas definidas no banco de dados.")
        else:
            print(f"Erro ao importar dados da planilha '{sheet_name}' para '{table_name}': {e}")