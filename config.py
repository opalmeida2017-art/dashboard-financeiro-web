# config.py (Versão Final e Corrigida)

TABLE_COLUMN_MAPS = {
    'relFilViagensFatCliente': {
        'date_formats': {
            'dataViagemMotorista': None, 'cteDataReciboEnv': None, 'dataChegouSaldo': None, 'dataEmissao': None, 'dataEncerramento': None,
            'dataFatPagAdiant': None, 'dataFatPagSaldo': None, 'dataFatSaldo': None, 'dataINS': None, 'dataNascimentoMot': None, 
            'dataPagtoDuplicatas': None, 'dataPrevDescarga': None, 'dataVencAdiant': None, 'dataVencSaldo': None
        },
        'numeric': [ 'COFINS', 'CSLL', 'PIS', 'acertoSaldo', 'adiantamentoEmp2', 'adiantamentoEmpresa', 'adiantamentoMotorista', 'adtoMot2', 'baseISS', 'cargaDescarga', 'descCSLLSaldoEmp', 'descCofinsSaldoEmp', 'descColeta', 'descDifFrete', 'descEntrega', 'descIRRFSaldoEmp', 'descPISSaldoEmp', 'descPedagioBaseMot', 'descSeguro2Saldo', 'descSeguro2SaldoMot', 'descSeguroSaldo', 'descSeguroSaldoMot', 'descSestSenatSaldoEmp', 'despesaExtra', 'fEmp', 'faturaICMSFinal', 'faturaPesoChegada', 'faturamento', 'freteCombinado', 'freteEmpresa', 'freteEmpresaComp', 'freteEmpresaSai', 'freteMotorista', 'freteMotoristaSai', 'kmFim', 'kmIni', 'kmParc', 'kmRodado', 'outrosDescontos', 'outrosDescontosMot', 'outrosDescontosMot2', 'percRedVLICMS', 'pesoChegada', 'pesoSaida', 'pesoSaidaMotorista', 'precoTonEmpresa', 'precoTonMotorista', 'premioSeguro', 'premioSeguro2', 'quantMercadoria', 'quantidadeQuebra', 'saldoEmp', 'saldoMotorista', 'somaFreteEmpresaComICMS', 'taxaAdiantEmpresa', 'vPercARet', 'valorAbonoQuebra', 'valorBalsa', 'valorClassificacao', 'valorEstadia', 'valorFreteEmpresaICMS', 'valorFreteFiscal', 'valorICMS', 'valorICMSNaoEmb', 'valorINSS', 'valorINSSEmpresa', 'valorIRRF', 'valorISS', 'valorPedagio', 'valorQuebra', 'valorRastreamento', 'valorSestSenat', 'valorTotalDPsPagoViagem', 'vlARec', 'vlAfat', 'vlCOFINS', 'vlCSLL', 'vlFaturado', 'vlPIS', 'vlRec', 'cubagem' ],
        'integer': [ 'codAcertoProprietario', 'codCliente', 'codClientePrincipal', 'codDest', 'codFatPagAdiant', 'codFatPagSaldo', 'codFaturaAdiantEmp2', 'codFaturaAdiantamento', 'codFaturaClassificacao', 'codFaturaEstadia', 'codFaturaICMS', 'codFaturaPedagio', 'codFaturaSaldo', 'codFaturaSaldoComp', 'codFilial', 'codFornecedorAdiant', 'codFornecedorClassificacao', 'codFornecedorICMS', 'codFornecedorPedagio', 'codFornecedorSaldo', 'codManif', 'codMercadoria', 'codProp', 'codRem', 'codTipoCliente', 'codTransAdiant', 'codTransEstadia', 'codTransICMS', 'codTransPedagio', 'codTransSaldo', 'codVeiculo', 'numConhec' ]
    },
    'relFilViagensCliente': {},
    'relFilDespesasGerais': {
        'numeric': ['custoTotal', 'valorNota'], 'integer': []
    },
    'relFilContasPagarDet': {
        'numeric': ['valorVenc'], 'integer': []
    },
    'relFilContasReceber': {
        'numeric': ['valorVenc'], 'integer': ['numConhec', 'numContabil']
    }
}

EXCEL_FILES_CONFIG = {
    "viagens_cliente": { "path": "relFilViagensCliente.xls", "sheet_name": "Viagens", "table_name": "relFilViagensCliente" },
    "viagens": { "path": "relFilViagensFatCliente.xls", "sheet_name": "Faturamento de Viagens por Clie", "table_name": "relFilViagensFatCliente" },
    "despesas": { "path": "relFilDespesasGerais.xls", "sheet_name": "Despesas Gerais", "table_name": "relFilDespesasGerais" },
    "contas_pagar": { "path": "relFilContasPagarDet.xls", "sheet_name": "NFeCompleto", "table_name": "relFilContasPagarDet" },
    "contas_receber": { "path": "relFilContasReceber.xls", "sheet_name": "ContasRecRecebNormal", "table_name": "relFilContasReceber" }
}

FILTER_COLUMN_MAPS = { "placa": ['placaVeiculo', 'placa'], "filial": ['nomeFilial', 'nomeFil'] }


# NOVO: Define as colunas que identificam uma linha única em cada tabela
TABLE_PRIMARY_KEYS = {
    "relFilViagensCliente": ["numConhec"],
    "relFilViagensFatCliente": ["numConhec"],
    "relFilDespesasGerais": ["numNota", "dataControle", "nomeForn"],
    "relFilContasPagarDet": ["numNota", "dataVenc", "nomeForn"],
    "relFilContasReceber": ["codDuplicataReceber"]
}
