/**
 * Relatório de viagem — modal HTML com destaques DRE (tipo frete, frete, custo, lucro).
 * Disponível em todas as páginas via layout.html.
 */
(function () {
    "use strict";

    function formatCurrency(value) {
        const n = Number(value);
        const safe = Number.isFinite(n) ? n : 0;
        return safe.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    }

    function lucroClass(valor) {
        return Number(valor) < 0 ? "rel-lucro-neg" : "rel-lucro-pos";
    }

    function dreFlagBadge(label, flagVal, isOk) {
        const cls = isOk ? "bg-success" : "bg-danger";
        const text = flagVal || (isOk ? "S" : "N");
        return `<span class="badge ${cls} text-white me-2">${label}: ${text}</span>`;
    }

    function buildRelatorioFlagsHtml(data) {
        return `<div class="d-flex flex-wrap gap-2 p-2 mb-2 rounded border bg-light">
            ${dreFlagBadge("Permite faturar", data.permite_faturar_flag, data.permite_faturar)}
            ${dreFlagBadge("Pagar conhecimento", data.pagar_flag, data.pagar_conhecimento)}
        </div>`;
    }

    function buildRelatorioReceitasHtml(data) {
        const pedagioInfo = (data.pedagio_reembolso || 0) > 0
            ? `<tr><td colspan="2" class="small text-muted border-0 pt-0">
                Pedágio ${formatCurrency(data.pedagio_reembolso)} — reembolso (fatura cliente / CP; não compõe receita).
            </td></tr>` : "";
        let freteRows;
        if (data.modo_proprietario) {
            freteRows = data.permite_faturar
                ? `<tr><td>Frete motorista (receita)</td><td class="text-end rel-valor-frete">${formatCurrency(data.frete_bruto)}</td></tr>`
                : `<tr><td>Frete motorista no CT-e <span class="small text-muted">— não compõe receita</span></td>
                   <td class="text-end rel-valor-frete">${formatCurrency(data.fretemotorista_bruto || 0)}</td></tr>
                   <tr><td>Receita contabilizada</td><td class="text-end">${formatCurrency(0)}</td></tr>`;
            freteRows += `<tr><td>Frete empresa no CT-e <span class="small text-muted">— referência</span></td>
                <td class="text-end">${formatCurrency(data.frete_empresa_bruto || 0)}</td></tr>`;
        } else {
            freteRows = data.permite_faturar
                ? `<tr><td>Frete empresa (receita)</td><td class="text-end rel-valor-frete">${formatCurrency(data.frete_bruto)}</td></tr>`
                : `<tr><td>Frete empresa no CT-e <span class="small text-muted">— não compõe receita</span></td>
                   <td class="text-end rel-valor-frete">${formatCurrency(data.frete_empresa_bruto || 0)}</td></tr>
                   <tr><td>Receita contabilizada</td><td class="text-end">${formatCurrency(0)}</td></tr>`;
        }
        return `<table class="table table-bordered table-sm mt-3 rel-viagem-table">
            <tr class="table-secondary"><th colspan="2">Receitas</th></tr>
            ${freteRows}
            ${pedagioInfo}
            <tr class="table-success fw-bold"><td>TOTAL RECEITAS</td><td class="text-end">${formatCurrency(data.total_receitas)}</td></tr>
        </table>`;
    }

    function buildRelatorioCustosPreviaHtml(data) {
        const pagar = !!data.pagar_conhecimento;
        const aviso = pagar
            ? `<tr><td colspan="2" class="small text-muted border-0">pagar = S — comissão e quebra não vão para contas a pagar.</td></tr>`
            : `<tr><td colspan="2" class="small text-warning border-0 bg-warning-subtle">
                pagar = N — custos prévia zerados no resultado. Valores <em>ref.</em> são só referência do CT-e.
            </td></tr>`;
        const row = (label, val, showRef) => {
            if (!val || val <= 0) return "";
            const ref = showRef ? ' <em class="text-muted small">ref.</em>' : "";
            const cls = showRef ? "text-muted" : "text-danger";
            return `<tr><td>(-) ${label}${ref}</td><td class="text-end ${cls}">${formatCurrency(val)}</td></tr>`;
        };
        const icms = pagar ? data.custo_icms : data.custo_icms_potencial;
        const seg = pagar ? data.custo_seguro : data.custo_seguro_potencial;
        const subLabel = pagar ? "Subtotal prévia" : 'Subtotal prévia <span class="text-muted small">(contabilizado: R$ 0)</span>';
        const custoPot = data.custo_previa_potencial || 0;
        const mot = pagar ? data.custo_motorista : data.custo_motorista_potencial;
        const modoProp = !!data.modo_proprietario;

        let composicaoHtml = "";
        if (!modoProp) {
            const comp = data.composicao_motorista || [];
            if (comp.length) {
                composicaoHtml = comp.map(function (linha) {
                    let cls = "";
                    if (linha.tipo === "resultado") cls = "fw-bold text-danger";
                    else if (linha.tipo === "desconto") cls = "ps-3 small text-muted";
                    else if (linha.tipo === "subtotal") cls = "fw-semibold";
                    else if (linha.tipo === "comissao") cls = "ps-3 text-danger";
                    else if (linha.tipo === "info") cls = "small text-muted fst-italic";
                    return `<tr><td class="${cls}">${linha.label}</td><td class="text-end ${linha.tipo === "resultado" ? "text-danger fw-bold" : ""}">${formatCurrency(linha.valor)}</td></tr>`;
                }).join("");
            } else {
                composicaoHtml = row("Frete motorista líquido", mot, !pagar);
            }
            composicaoHtml = `<tr class="table-light"><td colspan="2" class="small fw-semibold">Composição frete motorista</td></tr>${composicaoHtml}${row("ICMS embutido", icms, !pagar)}`;
        } else {
            composicaoHtml = `<tr><td colspan="2" class="small text-muted border-0">Modo proprietário: frete motorista e ICMS compõem a receita (não entram como custo).</td></tr>`;
        }

        return `<table class="table table-bordered table-sm mt-3 rel-viagem-table">
            <tr class="table-secondary"><th colspan="2">Custos Prévia (conhecimento)</th></tr>
            ${aviso}
            ${composicaoHtml}
            ${row("Seguro (não embutido no saldo)", seg, !pagar)}
            <tr class="table-warning fw-bold"><td>${subLabel}</td><td class="text-end rel-valor-custo-pot">${formatCurrency(data.custo_previa_conhecimento || 0)}</td></tr>
            <tr><td>Custo prévia potencial (CT-e)</td><td class="text-end rel-valor-custo-pot">${formatCurrency(custoPot)}</td></tr>
        </table>`;
    }

    function createItemsTableHtml(title, itemsArray, totalValue, tableClass, numero) {
        const headers = `
            <thead class="table-secondary">
                <tr>
                    <th style="width: 15%;">Grupo</th><th style="width: 8%;">Nota</th>
                    <th style="width: 10%;">Data</th><th style="width: 5%;">Série</th>
                    <th style="width: 20%;">Fornecedor</th><th style="width: 8%;">Cód. Item</th>
                    <th>Descrição</th><th class="text-end" style="width: 10%;">Valor</th>
                    <th class="text-center" style="width: 5%;">Ação</th>
                </tr>
            </thead>`;
        let rowsHtml = (itemsArray || []).map(function (item) {
            const showActionButton = item.codItemNota && item.descGrupoD !== "VALOR QUEBRA" && item.descGrupoD !== "COMISSÃO DE MOTORISTA";
            return `<tr>
                <td>${item.descGrupoD || ""}</td><td>${item.codNota || ""}</td>
                <td>${item.dataControle || ""}</td><td>${item.serie || ""}</td>
                <td>${item.nomeForn || ""}</td><td>${item.codItemNota || ""}</td>
                <td>${item.descItemD || ""}</td><td class="text-end">${formatCurrency(item.valor_calculado)}</td>
                <td class="text-center">
                    ${showActionButton ? `<button class="btn btn-warning btn-sm btn-desvincular-despesa" data-numero="${numero}" data-coditemnota="${item.codItemNota}">X</button>` : ""}
                </td>
            </tr>`;
        }).join("");
        if (!rowsHtml) {
            rowsHtml = `<tr><td colspan="9" class="text-center">Nenhum item encontrado.</td></tr>`;
        }
        return `<h4 class="mt-4">${title}</h4>
            <table class="table table-bordered table-sm rel-viagem-table">
                ${headers}
                <tbody>${rowsHtml}</tbody>
                <tfoot><tr class="${tableClass}" style="font-weight: bold;"><td colspan="8" class="text-end">TOTAL</td><td class="text-end">${formatCurrency(totalValue)}</td></tr></tfoot>
            </table>`;
    }

    function createSugestoesTableHtml(sugestoes, numero, periodo) {
        const periodoTxt = periodo && periodo.inicio
            ? `<p class="small text-muted"><strong>Período:</strong> ${periodo.inicio}${periodo.fim && periodo.fim !== periodo.inicio ? " a " + periodo.fim : ""}${periodo.proxima_viagem ? " (próxima viagem da placa: " + periodo.proxima_viagem + ")" : ""}. Não afeta o cálculo do resultado.</p>`
            : "<p class=\"small text-muted\">Despesas da placa entre esta viagem e a próxima (não afeta o cálculo).</p>";
        if (!sugestoes || sugestoes.length === 0) {
            return `<div class="no-print"><h4 class="mt-4">Sugestão de despesas</h4>${periodoTxt}<p>Nenhuma despesa sugerida no período.</p></div>`;
        }
        let totalSugestoes = 0;
        const headers = `
            <thead class="table-light">
                <tr>
                    <th>Grupo</th><th>Nota</th><th>Data</th><th>Série</th>
                    <th>Fornecedor</th><th>Cód. Item</th><th>Descrição</th>
                    <th style="text-align: right;">Valor</th><th>Ação</th>
                </tr>
            </thead>`;
        const rowsHtml = sugestoes.map(function (item) {
            totalSugestoes += parseFloat(item.Valor) || 0;
            return `<tr>
                <td>${item.descGrupoD || ""}</td><td>${item.codNota || ""}</td>
                <td>${item.dataControle || ""}</td><td>${item.serie || ""}</td>
                <td>${item.nomeForn || ""}</td><td>${item.codItemNota || ""}</td>
                <td>${item.descItemD || ""}</td><td style="text-align: right;">${formatCurrency(item.Valor)}</td>
                <td><button class="btn btn-success btn-sm btn-adicionar-despesa" data-numero="${numero}" data-coditemnota="${item.codItemNota}">Adicionar</button></td>
            </tr>`;
        }).join("");
        return `<div class="no-print">
            <h4 class="mt-4">Sugestão de despesas</h4>
            ${periodoTxt}
            <table class="table table-bordered table-sm rel-viagem-table">
                ${headers}
                <tbody>${rowsHtml}</tbody>
                <tfoot>
                    <tr style="font-weight: bold;">
                        <td colspan="8" style="text-align: right;">TOTAL DAS SUGESTÕES</td>
                        <td style="text-align: right;">${formatCurrency(totalSugestoes)}</td>
                        <td></td>
                    </tr>
                </tfoot>
            </table>
        </div>`;
    }

    function buildRelatorioHtml(data, numero) {
        const dataViagemFmt = data.data_viagem
            ? (window.BIWEBCharts?.fmtDataBr
                ? window.BIWEBCharts.fmtDataBr(data.data_viagem)
                : new Date(data.data_viagem).toLocaleDateString("pt-BR", { timeZone: "UTC" }))
            : "N/A";
        const tipoFrete = data.tipo_frete_label || data.tipo_frete || "—";
        const lucroCls = lucroClass(data.lucro_prejuizo_valor);
        const margemCls = lucroClass(data.margem_valor);
        const resumoFreteLabel = data.modo_proprietario ? "Frete motorista" : "Frete empresa";
        const resumoFreteVal = data.modo_proprietario
            ? (data.frete_bruto || data.fretemotorista_bruto || 0)
            : (data.frete_empresa_bruto || data.frete_bruto || 0);
        const resultadoHtml = `
            <table class="table table-bordered table-sm mt-3 rel-viagem-table">
                <tr class="table-secondary"><th colspan="2">Resultado da Viagem</th></tr>
                <tr><td>Total Receitas</td><td class="text-end">${formatCurrency(data.total_receitas)}</td></tr>
                <tr><td>(-) Custos prévia conhecimento</td><td class="text-end text-danger">${formatCurrency(data.custo_previa_conhecimento || 0)}</td></tr>
                <tr><td>(-) Outros custos (notas)</td><td class="text-end text-danger">${formatCurrency(data.total_outros_custos)}</td></tr>
                <tr><td>(-) Despesas da viagem (notas)</td><td class="text-end text-danger">${formatCurrency(data.total_despesas)}</td></tr>
                <tr><td>(-) Outros descontos</td><td class="text-end text-danger">${formatCurrency(data.outros_descontos)}</td></tr>
                <tr class="fw-bold"><td>LUCRO/PREJUÍZO</td><td class="text-end ${lucroCls}">${formatCurrency(data.lucro_prejuizo_valor)}</td></tr>
                <tr class="fw-bold"><td>MARGEM (%)</td><td class="text-end ${margemCls}">${(data.margem_valor || 0).toFixed(2).replace(".", ",")}%</td></tr>
            </table>`;

        return `
            <div class="rel-viagem-report">
                <div class="text-center mb-3"><h2>Relatório de Viagem</h2></div>
                <div class="rel-viagem-resumo mb-3 p-2 rounded border">
                    <div class="row g-2 text-center">
                        <div class="col-6 col-md-3"><span class="rel-resumo-label">Tipo frete</span><div class="rel-tipo-frete">${tipoFrete}</div></div>
                        <div class="col-6 col-md-3"><span class="rel-resumo-label">${resumoFreteLabel}</span><div class="rel-valor-frete">${formatCurrency(resumoFreteVal)}</div></div>
                        <div class="col-6 col-md-3"><span class="rel-resumo-label">Custo prévia pot.</span><div class="rel-valor-custo-pot">${formatCurrency(data.custo_previa_potencial || 0)}</div></div>
                        <div class="col-6 col-md-3"><span class="rel-resumo-label">Lucro / Prejuízo</span><div class="${lucroCls}">${formatCurrency(data.lucro_prejuizo_valor)}</div></div>
                    </div>
                </div>
                <table class="table table-bordered table-sm rel-viagem-table">
                    <tr>
                        <th style="width: 25%;">Viagem (CT-e)</th><td style="width: 25%;">${data.viagem_display}</td>
                        <th style="width: 25%;">Data Viagem</th><td style="width: 25%;">${dataViagemFmt}</td>
                    </tr>
                    <tr>
                        <th>Veículo</th><td>${data.placa_veiculo || "N/A"}</td>
                        <th>Motorista</th><td>${data.motorista || "N/A"}</td>
                    </tr>
                    <tr>
                        <th>Tipo frete</th><td class="rel-tipo-frete">${tipoFrete}</td>
                        <th>Filial</th><td>${data.filial}</td>
                    </tr>
                    <tr>
                        <th>Numero Nota</th><td>${data.numero_nota}</td>
                        <th>Unidade de Embarque</th><td>${data.unidade_embarque}</td>
                    </tr>
                </table>
                <table class="table table-bordered table-sm mt-3 rel-viagem-table">
                    <tr class="table-secondary"><th colspan="2">Dados da Viagem</th></tr>
                    <tr><th>Cliente</th><td>${data.cliente || "N/A"}</td></tr>
                    <tr><th>Origem &rarr; Destino</th><td>${data.origem || "N/A"} &rarr; ${data.destino || "N/A"}</td></tr>
                    <tr><th>Peso Saída / Chegada</th><td>${(data.peso_saida || 0).toLocaleString("pt-BR")} / ${(data.peso_chegada || 0).toLocaleString("pt-BR")} Kg</td></tr>
                    <tr><th>Valor Seguro</th><td>${formatCurrency(data.valor_seguro)}</td></tr>
                    <tr><th>Valor Pedágio</th><td>${formatCurrency(data.valor_pedagio || 0)} <span class="small text-muted">(embutido frete: ${data.pedagio_embutido_frete || "—"} / mot.: ${data.pedagio_embutido_motorista || "—"})</span></td></tr>
                    <tr><th>Valor Quebra</th><td>${formatCurrency(data.valor_quebra_bruto || data.valor_quebra || 0)}</td></tr>
                    <tr><th>KM Inicial</th><td>${(data.km_inicial || 0).toLocaleString("pt-BR")}</td></tr>
                    <tr><th>KM Final</th><td>${(data.km_final || 0).toLocaleString("pt-BR")}</td></tr>
                    <tr><th>KM Rodado</th><td>${(data.km_rodado || 0).toLocaleString("pt-BR")} Km</td></tr>
                    <tr><th>Base comissão</th><td>${formatCurrency(data.valor_base_comissao)} <span class="small text-muted">${(data.comissao_perc || 0).toLocaleString("pt-BR")}% → ${formatCurrency(data.valor_comissao_calculada || data.comissao_motorista || 0)}</span></td></tr>
                </table>
                ${buildRelatorioFlagsHtml(data)}
                ${buildRelatorioReceitasHtml(data)}
                ${buildRelatorioCustosPreviaHtml(data)}
                ${createItemsTableHtml("Outros Custos da Viagem", data.custos_detalhados, data.total_outros_custos, "table-warning", numero)}
                ${createItemsTableHtml("Despesas da Viagem", data.despesas_detalhadas, data.total_despesas, "table-danger", numero)}
                ${resultadoHtml}
                ${createSugestoesTableHtml(data.despesas_sugeridas, numero, data.periodo_sugestao_despesas)}
            </div>`;
    }

    function getDiasJanela() {
        const el = document.getElementById("dias-busca-sugestao");
        return (el && el.value) ? el.value : 10;
    }

    function openRelatorioViagem(numero) {
        const relatorioModal = document.getElementById("relatorioViagemModal");
        const relatorioBody = document.getElementById("relatorio-body");
        if (!relatorioModal || !relatorioBody) {
            console.warn("Modal de relatório não encontrado.");
            return;
        }

        relatorioBody.innerHTML = "<p class=\"text-center\">Buscando dados da viagem...</p>";
        const btnPrint = relatorioModal.querySelector("#btnPrintReport");
        if (btnPrint) btnPrint.dataset.numero = numero;

        const conhecimentosModal = document.getElementById("conhecimentosModal");
        if (conhecimentosModal) conhecimentosModal.style.display = "none";
        const biAuditModal = document.getElementById("biAuditModal");
        if (biAuditModal) biAuditModal.style.display = "none";
        relatorioModal.style.display = "block";
        relatorioModal.style.zIndex = "1100";

        const apiUrl = "/api/relatorio_viagem/" + encodeURIComponent(numero) + "?dias_janela=" + encodeURIComponent(getDiasJanela()) + "&format=json";

        fetch(apiUrl, {
            headers: {
                Accept: "application/json",
                "X-BIWEB-Client": "relatorio-modal",
            },
        })
            .then(function (response) {
                if (!response.ok) throw new Error("Erro de rede: " + response.statusText);
                return response.json();
            })
            .then(function (data) {
                if (data.error) {
                    relatorioBody.innerHTML = "<p class=\"text-center text-danger\">Erro: " + data.error + "</p>";
                    return;
                }
                relatorioBody.innerHTML = buildRelatorioHtml(data, numero);
            })
            .catch(function (error) {
                relatorioBody.innerHTML = "<p class=\"text-center text-danger\">Ocorreu um erro ao buscar os dados: " + error + "</p>";
            });
    }

    function initRelatorioViagem() {
        const relatorioModal = document.getElementById("relatorioViagemModal");
        if (!relatorioModal) return;

        const btnPrint = relatorioModal.querySelector("#btnPrintReport");
        if (btnPrint && !btnPrint.dataset.relInit) {
            btnPrint.dataset.relInit = "1";
            btnPrint.addEventListener("click", function () {
                const numeroViagem = this.dataset.numero;
                if (numeroViagem) {
                    window.open("/report/print/" + encodeURIComponent(numeroViagem), "_blank");
                } else {
                    alert("Erro: Não foi possível identificar o número da viagem para impressão.");
                }
            });
        }

        if (!relatorioModal.dataset.relInit) {
            relatorioModal.dataset.relInit = "1";
            relatorioModal.addEventListener("click", function (event) {
                const button = event.target.closest("button");
                if (!button || (!button.classList.contains("btn-adicionar-despesa") && !button.classList.contains("btn-desvincular-despesa"))) return;

                const numero = button.dataset.numero;
                const codItemNota = button.dataset.coditemnota;
                const isAdd = button.classList.contains("btn-adicionar-despesa");
                const apiUrl = isAdd ? "/api/associar_despesa_viagem" : "/api/desvincular_despesa_viagem";

                button.disabled = true;
                button.textContent = isAdd ? "..." : "X";

                fetch(apiUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ numero: numero, cod_item_nota: codItemNota }),
                })
                    .then(function (response) {
                        if (!response.ok) {
                            alert("Erro de comunicação com o servidor.");
                            return Promise.reject("API falhou");
                        }
                        return response.json();
                    })
                    .then(function (data) {
                        if (data.status === "success") {
                            openRelatorioViagem(numero);
                        } else {
                            alert("Erro: " + (data.message || "Ação falhou"));
                            button.disabled = false;
                        }
                    })
                    .catch(function () {
                        button.disabled = false;
                    });
            });
        }

        const closeBtn = relatorioModal.querySelector(".close-button");
        if (closeBtn && !closeBtn.dataset.relInit) {
            closeBtn.dataset.relInit = "1";
            closeBtn.addEventListener("click", function () {
                relatorioModal.style.display = "none";
            });
        }
    }

    window.BIWEB_openRelatorioViagem = openRelatorioViagem;

    document.addEventListener("DOMContentLoaded", initRelatorioViagem);
})();
