# config.py (Versão Final e Corrigida)

TABLE_COLUMN_MAPS = {
    'relFilViagensFatCliente': {
        'date_formats': {
            'dataViagemMotorista': None, 'cteDataReciboEnv': None, 'dataEmissao': None, 'dataEmissaoComHora': None,
            'dataINS': None, 'dataNascimentoProp': None, 'dataPrevDescarga': None, 'dataPrevEntrega': None
        },
        'numeric': [
            'acertoSaldo', 'adValor', 'adiantamentoMotorista', 'adtoMot2', 'aliquotaCofins', 'aliquotaIss',
            'aliquotaPis', 'baseICMS', 'baseImpostos', 'baseIss', 'cargaDescarga', 'comissao', 'despesaExtra',
            'despesasadicionais', 'fTotalPrest', 'faturaICMSFinal', 'faturaPesoChegada', 'freteEmpresa',
            'freteEmpresaSai', 'freteMotorista', 'freteMotoristaSai', 'margemFrete', 'margemFretePerc',
            'outrosDescontos', 'outrosDescontosMot', 'outrosDescontosMot2', 'percRedVLICMS', 'pesoChegada',
            'pesoSaida', 'pesoSaidaMotorista', 'porcICMS', 'precoKgMercQuebra', 'precoMercadoria',
            'precoTonEmpresa', 'precoTonFiscal', 'precoTonMotorista', 'premioSeguro', 'premioSeguro2',
            'quantMercadoria', 'quantidadeQuebra', 'quebraTotal', 'saldoMotorista', 'taxaQuebra',
            'toleranciaPesoCheg', 'valorAbonoQuebra', 'valorBalsa', 'valorClassificacao', 'valorCofins',
            'valorEstadia', 'valorFreteFiscal', 'valorICMS', 'valorINSS', 'valorIRRF', 'valorIss',
            'valorMercadoria', 'valorPedagio', 'valorPis', 'valorQuebra', 'valorSeguro', 'valorSeguro2',
            'valorSestSenat', 'valorTotalnf', 'vlIcms', 'vlTotalPrestacaoDacte'
        ],
        'integer': [
            'codClDest', 'codClRemet', 'codCliente', 'codColetaEntregaAg', 'codEmpresas', 'codFaturaSaldo',
            'codFilial', 'codMercadoria', 'codOrdemCar', 'codProp', 'codRota', 'codServicoNfs', 'codUnidadeEmb',
            'numConhec', 'numConhecColEntrega', 'numNF', 'numNotaNF', 'numPedido'
        ]
    },
    'relFilViagensCliente': {
        'date_formats': {
            'cteDataReciboEnv': None, 'dataALT': None, 'dataEmissao': None, 'dataEmissaoComHora': None,
            'dataINS': None, 'dataNascimentoProp': None, 'dataPrevDescarga': None, 'dataPrevEntrega': None,
            'dataVencSaldo': None, 'dataViagemMotorista': None
        },
        'numeric': [
            'adValor', 'adiantamentoEmpresa', 'adiantamentoMotorista', 'adtoMot2', 'aliquotaCofins',
            'aliquotaIss', 'aliquotaPis', 'baseICMS', 'baseImpostos', 'baseIss', 'cargaDescarga',
            'comissao', 'despesaExtra', 'despesasadicionais', 'fTotalPrest', 'faturaPesoChegada',
            'freteEmpresa', 'freteEmpresaComp', 'freteEmpresaSai', 'freteMotorista', 'freteMotoristaSai',
            'margemFrete', 'margemFretePerc', 'outrosDescontos', 'outrosDescontosMot', 'outrosDescontosMot2',
            'percRedVLICMS', 'pesoChegada', 'pesoSaida', 'porcICMS', 'precoKgMercQuebra', 'precoMercadoria',
            'precoTonEmpresa', 'precoTonFiscal', 'precoTonMotorista', 'premioSeguro', 'premioSeguro2',
            'quantMercadoria', 'quantidadeQuebra', 'quebraTotal', 'saldoEmp', 'saldoMotorista', 'taxaQuebra',
            'valorAbonoQuebra', 'valorBalsa', 'valorClassificacao', 'valorCofins', 'valorEstadia',
            'valorFreteFiscal', 'valorICMS', 'valorINSS', 'valorIRRF', 'valorIss', 'valorMercadoria',
            'valorPedagio', 'valorPis', 'valorQuebra', 'valorSeguro', 'valorSeguro2', 'valorSestSenat',
            'valorTotalnf', 'vlIcms', 'vlTotalPrestacaoDacte'
        ],
        'integer': [
            'apartamento_id', 'codClDest', 'codClRemet', 'codCliente', 'codColetaEntregaAg', 'codEmpresas',
            'codFaturaSaldo', 'codFilial', 'codMercadoria', 'codOrdemCar', 'codProp', 'codRota',
            'codServicoNfs', 'codUnidadeEmb', 'numConhec', 'numeroConhecimento'
        ]
    },
    'relFilDespesasGerais': {
        'date_formats': {
            'dataAcertoProp': None, 'dataControle': None, 'dataControleFormat': None, 'dataEmissao': None,
            'dataFim': None, 'dataFimOficina': None, 'dataINS': None, 'dataIniOficina': None,
            'dataMotorista': None, 'dataVenc': None, 'dataVencimento': None
        },
        'numeric': [
            'custo', 'custoTotal', 'desconto', 'km', 'kmAnterior', 'kmPrev', 'kmRodado', 'kmRodadoDec',
            'liquido', 'mediaDesejada', 'mediaKm', 'mediaMax', 'mediaMin', 'porcAliqIcmsSubsTribItem',
            'porcIcmsItem', 'porcIpiItem', 'quantidade', 'valor', 'valorAcertoProp', 'valorBaseIcmsItem',
            'valorBaseIpiItem', 'valorBaseSubsTribItem', 'valorDescontoItem', 'valorDespesa',
            'valorFaturamento', 'valorFrete', 'valorFreteEmp', 'valorFreteMot', 'valorIcmsItem',
            'valorImpSfed', 'valorIpiItem', 'valorIss', 'valorItem', 'valorMargem', 'valorNota',
            'valorOutras', 'valorPesoSaidaTon', 'valorProd', 'valorReceitaOp', 'valorResultado',
            'valorResultadoComInv', 'valorSeguro', 'valorServ', 'valorSubsTribItem', 'valorUnit',
            'valorVenc', 'vlBaseIcms', 'vlBaseIcmsSubstTrib', 'vlCofinsRet', 'vlContabil',
            'vlCreditoIcms', 'vlCsllRet', 'vlIcms', 'vlIcmsSubstTrib', 'vlInssRet', 'vlIpi',
            'vlIrrfRet', 'vlPisRet'
        ],
        'integer': [
            'apartamento_id', 'codAcertoMotorista', 'codAcertoProprietario', 'codAdiantamento', 'codAgrupador',
            'codCavalo', 'codCfop', 'codCfopItem', 'codCliente', 'codContaContabil', 'codEmonitor',
            'codEmpresas', 'codFatura', 'codFaturaReceber', 'codFilial', 'codForn', 'codFornProp',
            'codGrupoD', 'codIBGECidC', 'codIBGECidF', 'codItemD', 'codItemDServico', 'codItemNota',
            'codMotNota', 'codMotorista', 'codNegocio', 'codNota', 'codProprietario', 'codSituacao',
            'codSuperGrupoD', 'codUeItem', 'codUnidadeEmbarque', 'codVeiculo', 'id'
        ]
    },
    'relFilContasPagarDet': {
        'date_formats': {
            'dataEmissao': None, 'dataLib': None, 'dataPagto': None, 'dataPagtoFormat': None,
            'dataPrevista': None, 'dataVenc': None
        },
        'numeric': [
            'kmItemNota', 'liquidoItemNota', 'pesoSaidaMotorista', 'premioSeguro',
            'quantidadeItemNota', 'totalTipoPagto', 'valorIcmsNota', 'valorImpSfedNota',
            'valorIssNota', 'valorNota', 'valorPagto', 'valorProporcional',
            'valorQuebra', 'valorVenc', 'vlCofinsRetNota', 'vlCsllRetNota',
            'vlFat', 'vlInssRetNota', 'vlIrrfRetNota', 'vlPisRetNota'
        ],
        'integer': [
            'apartamento_id', 'codAcertoProprietario', 'codBaixa', 'codCheque', 'codDuplicataPagar',
            'codEmpresas', 'codErpExterno', 'codFilial', 'codForn', 'codItemNota',
            'codNota', 'codTipoPagto', 'codTransacao', 'codUnidadeEmbarque',
            'numConhec', 'numNota'
        ]
    },
    'relFilContasReceber': {
        'date_formats': {
            'dataEmissao': None, 'dataPagto': None, 'dataVenc': None
        },
        'numeric': [
            'valorPagto', 'valorVenc'
        ],
        'integer': [
            'apartamento_id', 'codAcertoProprietario', 'codBaixa', 'codCliente',
            'codDuplicataReceber', 'codEmpresas', 'codFatura', 'codFilial',
            'codTransacao', 'numContabil'
        ]
    }
}

EXCEL_FILES_CONFIG = {
    "viagens_cliente": { "path": "relFilViagensCliente.xls", "sheet_name": "Viagens", "table": "relFilViagensCliente" },
    "viagens": { "path": "relFilViagensFatCliente.xls", "sheet_name": "Faturamento de Viagens por Clie", "table": "relFilViagensFatCliente" },
    "despesas": { "path": "relFilDespesasGerais.xls", "sheet_name": "Despesas Gerais", "table": "relFilDespesasGerais" },
    "contas_pagar": { "path": "relFilContasPagarDet.xls", "sheet_name": "NFeCompleto", "table": "relFilContasPagarDet" },
    "contas_receber": { "path": "relFilContasReceber.xls", "sheet_name": "ContasRecRecebNormal", "table": "relFilContasReceber" }
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