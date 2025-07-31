# config.py

# As variáveis APP_VERSION, VERSION_CHECK_URL, LICENSE_VALIDATION_URL e DATABASE_NAME foram removidas
# porque não são mais utilizadas pela aplicação web no ambiente de produção (Render).

TABLE_COLUMN_MAPS = {
    'relFilViagensFatCliente': {
        'date_formats': {
            'dataViagemMotorista': '%d/%m/%Y %H:%M:%S.%f',
            'cteDataReciboEnv': None, 'dataChegouSaldo': None, 'dataEmissao': None, 'dataEncerramento': None,
            'dataFatPagAdiant': None, 'dataFatPagSaldo': None, 'dataFatSaldo': None, 'dataINS': None,
            'dataNascimentoMot': None, 'dataPagtoDuplicatas': None, 'dataPrevDescarga': None,
            'dataVencAdiant': None, 'dataVencSaldo': None
        },
        'numeric': [
            'COFINS', 'CSLL', 'PIS', 'acertoSaldo', 'adiantamentoEmp2', 'adiantamentoEmpresa',
            'adiantamentoMotorista', 'adtoMot2', 'baseISS', 'cargaDescarga', 'descCSLLSaldoEmp',
            'descCofinsSaldoEmp', 'descColeta', 'descDifFrete', 'descEntrega', 'descIRRFSaldoEmp',
            'descPISSaldoEmp', 'descPedagioBaseMot', 'descSeguro2Saldo',
            'descSeguro2SaldoMot', 'descSeguroSaldo', 'descSeguroSaldoMot', 'descSestSenatSaldoEmp',
            'despesaExtra', 'fEmp', 'faturaICMSFinal', 'faturaPesoChegada', 'faturamento', 'freteCombinado',
            'freteEmpresa', 'freteEmpresaComp', 'freteEmpresaSai', 'freteMotorista', 'freteMotoristaSai',
            'kmFim', 'kmIni', 'kmParc', 'kmRodado', 'outrosDescontos', 'outrosDescontosMot',
            'outrosDescontosMot2', 'percRedVLICMS', 'pesoChegada', 'pesoSaida', 'pesoSaidaMotorista',
            'precoTonEmpresa', 'precoTonMotorista', 'premioSeguro', 'premioSeguro2', 'quantMercadoria',
            'quantidadeQuebra', 'saldoEmp', 'saldoMotorista', 'somaFreteEmpresaComICMS', 'taxaAdiantEmpresa',
            'vPercARet', 'valorAbonoQuebra', 'valorBalsa', 'valorClassificacao', 'valorEstadia',
            'valorFreteEmpresaICMS', 'valorFreteFiscal', 'valorICMS', 'valorICMSNaoEmb', 'valorINSS',
            'valorINSSEmpresa', 'valorIRRF', 'valorISS', 'valorPedagio', 'valorQuebra',
            'valorRastreamento', 'valorSestSenat', 'valorTotalDPsPagoViagem', 'vlARec', 'vlAfat',
            'vlCOFINS', 'vlCSLL', 'vlFaturado', 'vlPIS', 'vlRec', 'cubagem'
        ],
        'integer': [
            'codAcertoProprietario', 'codCliente', 'codClientePrincipal', 'codDest', 'codFatPagAdiant',
            'codFatPagSaldo', 'codFaturaAdiantEmp2', 'codFaturaAdiantamento', 'codFaturaClassificacao',
            'codFaturaEstadia', 'codFaturaICMS', 'codFaturaPedagio', 'codFaturaSaldo', 'codFaturaSaldoComp',
            'codFilial', 'codFornecedorAdiant', 'codFornecedorClassificacao', 'codFornecedorICMS',
            'codFornecedorPedagio', 'codFornecedorSaldo', 'codManif', 'codMercadoria', 'codProp',
            'codRem', 'codTipoCliente', 'codTransAdiant', 'codTransEstadia', 'codTransICMS',
            'codTransPedagio', 'codTransSaldo', 'codVeiculo', 'numConhec'
        ]
    },
    'relFilDespesasGerais': {
        'date_formats': {'dataEmissao': None, 'dataControle': None},
        'numeric': ['custoTotal', 'valorNota'],
        'integer': []
    },
    'relFilContasPagarDet': {
        'date_formats': {'dataEmissao': None, 'dataVenc': None, 'dataControle': None},
        'numeric': ['valorVenc'],
        'integer': []
    },
    'relFilContasReceber': {
        'date_formats': {'dataEmissao': None, 'dataVenc': None, 'dataViagemMotorista': None},
        'numeric': ['valorVenc'],
        'integer': ['numConhec', 'numContabil']
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

TABLE_VIEWS = {
    "relFilViagensFatCliente": [
        'dataViagemMotorista','numConhec', 'nomeCliente', 'nomeMot',
        'placaVeiculo', 'freteEmpresa', 'freteMotorista', 'saldoMotorista',
        'permiteFaturar', 'cidadeOrig', 'ufOrig', 'cidadeDest', 'ufDest'
    ],
    "relFilContasPagarDet": [ 'dataVenc', 'numNota', 'nomeForn', 'valorVenc', 'pago', 'nomeFil' ],
    "relFilContasReceber": [ 'dataVenc', 'numNF', 'nomeCliente', 'valorVenc', 'recebido', 'nomeFil' ]
}

# RECOMENDAÇÃO: No futuro, considere remover esta seção e fazer a validação de colunas
# dinamicamente, lendo o esquema diretamente do banco de dados após a criação das tabelas.
TABLE_COLUMNS_MASTER_LISTS = {
    'relFilViagensFatCliente': [ 'COFINS', 'CSLL', 'PIS', 'acertoSaldo', 'adiantamentoEmp2', 'adiantamentoEmpresa', 'adiantamentoMotorista', 'adtoMot2', 'agregado', 'baseISS', 'cargaDescarga', 'cepCliente', 'cidCliente', 'cidDest', 'cidEmpresas', 'cidOrig', 'cidadeClientePrincipal', 'cidadeDest', 'cidadeFil', 'cidadeRem', 'classificacaoEmbFreteEmp', 'clientePagaSaldoMotorista', 'cnpjCpfCliente', 'cnpjCpfEmpresas', 'cnpjCpfFil', 'cnpjCpfProp', 'codAcertoProprietario', 'codCheque', 'codCliente', 'codClientePrincipal', 'codDest', 'codFatPagAdiant', 'codFatPagSaldo', 'codFaturaAdiantEmp2', 'codFaturaAdiantamento', 'codFaturaClassificacao', 'codFaturaEstadia', 'codFaturaICMS', 'codFaturaPedagio', 'codFaturaSaldo', 'codFaturaSaldoComp', 'codFilial', 'codFornecedorAdiant', 'codFornecedorClassificacao', 'codFornecedorICMS', 'codFornecedorPedagio', 'codFornecedorSaldo', 'codManif', 'codMercadoria', 'codProp', 'codRem', 'codTipoCliente', 'codTransAdiant', 'codTransEstadia', 'codTransICMS', 'codTransPedagio', 'codTransSaldo', 'codVeiculo', 'complementoCliente', 'contrato', 'cpfMot', 'cteDataReciboEnv', 'cteStatus', 'cteStatusDesc', 'dataChegouSaldo', 'dataEmissao', 'dataEncerramento', 'dataFatPagAdiant', 'dataFatPagSaldo', 'dataFatSaldo', 'dataINS', 'dataNascimentoMot', 'dataPagtoDuplicatas', 'dataPrevDescarga', 'dataVencAdiant', 'dataVencSaldo', 'dataViagemMotorista', 'descCSLLSaldoEmp', 'descCofinsSaldoEmp', 'descColeta', 'descDifFrete', 'descEntrega', 'descIRRFSaldoEmp', 'descPISSaldoEmp', 'descPedagioBaseMot', 'descQuebraSaldoEmp', 'descSeguro2Saldo', 'descSeguro2SaldoMot', 'descSeguroSaldo', 'descSeguroSaldoMot', 'descSestSenatSaldoEmp', 'descontaICMSSaldoEmpresa', 'descontaINSSSaldo', 'descontaINSSSaldoMot', 'descontaISSSaldoEmp', 'descricaoMercadoria', 'despesaExtra', 'enderecoCliente', 'enderecoEmpresas', 'enderecoFil', 'estadiaEmbutidaFrete', 'fEmp', 'faturaICMSFinal', 'faturaPesoChegada', 'faturamento', 'faxEmpresas', 'faxFil', 'foneCliente', 'foneEmpresas', 'foneFil', 'freteCombinado', 'freteEmpresa', 'freteEmpresaComp', 'freteEmpresaSai', 'freteMotorista', 'freteMotoristaSai', 'historico1FatSaldo', 'historico2FatSaldo', 'historicoFatSaldo', 'horaFimDescarga', 'icmsEmbutido', 'inscEstCliente', 'issEmbutido', 'kmFim', 'kmIni', 'kmParc', 'kmRodado', 'liberadoOrdServ', 'nomeCliente', 'nomeClientePrincipal', 'nomeDest', 'nomeEmpresas', 'nomeFilial', 'nomeFornSaldo', 'nomeMot', 'nomeProp', 'nomeRem', 'numConhec', 'numNF', 'numPedido', 'numero', 'numeroClassificacao', 'numeroICMS', 'numeroProgramacao', 'obsFatSaldo', 'outrosDescontos', 'outrosDescontosMot', 'outrosDescontosMot2', 'pagaICMS', 'pedagioEmbutidoFrete', 'pedidoFrete', 'percRedVLICMS', 'permiteFaturar', 'permitePagarSaldoFrota', 'pesoChegada', 'pesoSaida', 'pesoSaidaMotorista', 'placa', 'placaVeiculo', 'precoTonEmpresa', 'precoTonMotorista', 'premioSeguro', 'premioSeguro2', 'quantMercadoria', 'quantidadeQuebra', 'quebraSegurada', 'saldoEmp', 'saldoMotorista', 'somaFreteEmpresaComICMS', 'somarISSFatSaldo', 'taxaAdiantEmpresa', 'tipoCte', 'tipoFat', 'tipoFrete', 'tributaImpostos', 'ufCidCliente', 'ufCidDest', 'ufCidFil', 'ufCidRem', 'ufClientePrincipal', 'ufDest', 'ufOrig', 'vPercARet', 'valorAbonoQuebra', 'valorBalsa', 'valorClassificacao', 'valorEstadia', 'valorFreteEmpresaICMS', 'valorFreteFiscal', 'valorICMS', 'valorICMSNaoEmb', 'valorINSS', 'valorINSSEmpresa', 'valorIRRF', 'valorISS', 'valorPedagio', 'valorQuebra', 'valorRastreamento', 'valorSestSenat', 'valorTotalDPsPagoViagem', 'veiculoProprio', 'vlARec', 'vlAfat', 'vlCOFINS', 'vlCSLL', 'vlFaturado', 'vlPIS', 'vlRec', 'custoTotal' ],
    'relFilDespesasGerais': [ 'afaturar','agencia','ano','anoMes','banco','box','cadNota','cavalo','cep','chaveNfe','cidadeEmpresas','cidadeFilial','cidadeForn','cnpjCpf','cnpjCpfEmpresas','cnpjCpfFil','cnpjCpfFilial','cnpjCpfForn','codAcertoMotorista','codAcertoProprietario','codAdiantamento','codAgrupador','codCavalo','codCfop','codCfopItem','codCliente','codContaContabil','codEmonitor','codEmpresas','codFatura','codFaturaReceber','codFilial','codForn','codFornProp','codGrupoD','codIBGECidC','codIBGECidF','codItemD','codItemDServico','codItemNota','codMotNota','codMotorista','codNegocio','codNota','codProprietario','codSituacao','codSuperGrupoD','codUeItem','codUnidadeEmbarque','codVeiculo','conta','contaContabil','contrato','creditaPisCofins','creditaPisCofinsItem','cstCOFINSItem','cstCOFINSItemD','cstICMSItemD','cstIcmsItem','cstPISItem','cstPISItemD','custo','custoTotal','dataAcertoProp','dataControle','dataControleFormat','dataEmissao','dataFim','dataFimOficina','dataINS','dataIniOficina','dataMotorista','dataVenc','dataVencimento','descCodFilial','descCodForn','descCodGrupoDItemNota','descCodItemDItemNota','descCodSuperGrupoDItemNota','descCodUnidadeEmbarque','descGrupoD','descItemD','descNegocio','descSuperGrupoD','descUeItem','descUnidadeEmbarque','desconto','despesa','endereco','especie','fontCenter','fontLeft','fontRight','frota','garantia','gerenciaEstoque','historico','id','incluiRateio','inic','inscEst','inscEstForn','investimento','km','kmAnterior','kmPrev','kmRodado','kmRodadoDec','liquido','listItensDespesas','marcaAux','marcaVeic','mediaDesejada','mediaInversa','mediaKm','mediaMax','mediaMin','modeloAux','modeloVeic','naoEncheuTanque','naoPrevista', 'nomeEmpresas', 'nomeFilial', 'nomeForn', 'nomeFornProp', 'nomeGrupoD', 'nomeItemD', 'nomeNegocio', 'nomeSuperGrupoD', 'nomeUeItem', 'nomeUnidadeEmbarque', 'numNota','numNotaFiscal','observacao','observacaoItem','pagamento','pagtoParcial','parcial','parcialItem','pessoa','pessoaForn','pesoBruto','pesoLiquido','placaVeiculo','precoUnitario','quantidade','quantidadeItemD','quantidadeItemNota','recebimento','recebimentoParcial','recebimentoParcialItem','referencia','referenciaItemD','referenciaItemNota','saldoDevedor','situacao','situacaoFormatada','subTotalPisCofinsItemD','subTotalPisCofinsItemNota','subTotalIcmsItemD','subTotalIcmsItemNota','subTotalIpiItemD','subTotalIpiItemNota','subTotalIssqnItemD','subTotalIssqnItemNota','superGrupoDItemNotaFormatado', 'totalPisCofinsItemD', 'totalPisCofinsItemNota', 'totalIcmsItemD', 'totalIcmsItemNota', 'totalIpiItemD', 'totalIpiItemNota', 'totalIssqnItemD', 'totalIssqnItemNota' ],
}