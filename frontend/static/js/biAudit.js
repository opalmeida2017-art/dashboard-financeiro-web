/**
 * Auditoria BI — modal com CT-es e itens de nota que compõem cada KPI.
 */
(function () {
    function fmtMoeda(v) {
        const n = Number(v);
        const safe = Number.isFinite(n) ? n : 0;
        return safe.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    }

    function getPageParams() {
        const params = new URLSearchParams(window.location.search);
        if (!params.get("start_date") || !params.get("end_date")) {
            const sd = document.getElementById("start_date")?.value;
            const ed = document.getElementById("end_date")?.value;
            if (sd) params.set("start_date", sd);
            if (ed) params.set("end_date", ed);
        }
        const placaEl = document.getElementById("placa");
        if (!params.get("placa") && placaEl?.value) params.set("placa", placaEl.value);
        const tipoEl = document.getElementById("tipo_negocio");
        if (!params.get("tipo_negocio") && tipoEl?.value) params.set("tipo_negocio", tipoEl.value);
        const embEl = document.getElementById("embarcador");
        if (!params.get("embarcador") && embEl?.value && embEl.value !== "Todos") {
            params.set("embarcador", embEl.value);
        }
        return params;
    }

    function renderTableCte(linhas, metric) {
        if (!linhas || !linhas.length) {
            return "";
        }
        const showReceita = metric === "receita_frete";
        const showCusto = ["custo_previa_conhecimento", "custo_operacional", "custo_viagem"].includes(metric);
        const rows = linhas
            .map((l) => {
                const excluido =
                    l.receita === 0 && l.frete_empresa_bruto > 0 && metric === "receita_frete";
                const flags = `fat ${l.permite_faturar || "—"} / pag ${l.pagarConhecimento || "—"}`;
                return `<tr class="${excluido ? "bi-audit-row-muted" : ""}">
                    <td>${l.display || l.numero}</td>
                    <td>${l.cliente || "—"}</td>
                    <td>${l.data_viagem || "—"}</td>
                    ${showReceita ? `<td class="text-end">${fmtMoeda(l.receita)}${excluido ? ' <span class="bi-audit-tag">não conta</span>' : ""}</td>` : ""}
                    ${showCusto ? `<td class="text-end">${fmtMoeda(l.custo_previa)}</td>` : ""}
                    <td class="small text-muted">${flags}</td>
                    <td class="text-center">
                        <button type="button" class="bi-audit-rel-btn" data-numero="${l.numero}" title="Relatório da viagem">↗</button>
                    </td>
                </tr>`;
            })
            .join("");

        return `<h6 class="bi-audit-section-title">CT-es</h6>
            <div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table">
                <thead class="table-secondary">
                    <tr>
                        <th>CT-e</th>
                        <th>Cliente</th>
                        <th>Data</th>
                        ${showReceita ? '<th class="text-end">Receita</th>' : ""}
                        ${showCusto ? '<th class="text-end">Custo prévia</th>' : ""}
                        <th>Flags</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderTableNotas(linhas, metric) {
        if (!linhas || !linhas.length) {
            return "";
        }
        const financeiro = metric === "contas_pagar" || metric === "contas_receber";
        const estoque = metric === "investimento_estoque";
        const rows = linhas
            .map((l) => {
                if (financeiro) {
                    return `<tr>
                        <td>${l.documento || "—"}</td>
                        <td>${l.vencimento || "—"}</td>
                        <td>${l.filial || "—"}</td>
                        <td class="text-end">${fmtMoeda(l.valor)}</td>
                    </tr>`;
                }
                if (estoque) {
                    return `<tr>
                        <td>${l.coditem != null ? l.coditem : "—"}</td>
                        <td class="small">${l.item || "—"}</td>
                        <td>${l.grupo || "—"}</td>
                        <td class="text-end">${l.saldo != null ? l.saldo : "—"}</td>
                        <td class="text-end">${fmtMoeda(l.valor)}</td>
                    </tr>`;
                }
                return `<tr>
                    <td>${l.nota || l.codnota || "—"}</td>
                    <td class="small">${l.cod_itemnota != null ? l.cod_itemnota : "—"}</td>
                    <td>${l.data || "—"}</td>
                    <td>${l.grupo || "—"}</td>
                    <td class="small">${l.item || "—"}</td>
                    <td class="text-center">${l.ved || "—"}</td>
                    <td>${l.placa || "—"}</td>
                    <td class="text-end">${fmtMoeda(l.valor)}</td>
                </tr>`;
            })
            .join("");

        if (financeiro) {
            return `<h6 class="bi-audit-section-title">Títulos em aberto</h6>
                <div class="table-responsive bi-audit-table-wrap">
                <table class="table table-sm table-bordered bi-audit-table">
                    <thead class="table-secondary">
                        <tr>
                            <th>Documento</th>
                            <th>Vencimento</th>
                            <th>Filial</th>
                            <th class="text-end">Valor</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
        }

        if (estoque) {
            return `<h6 class="bi-audit-section-title">Itens em estoque (investimento)</h6>
                <div class="table-responsive bi-audit-table-wrap">
                <table class="table table-sm table-bordered bi-audit-table">
                    <thead class="table-secondary">
                        <tr>
                            <th>Cód.</th>
                            <th>Item</th>
                            <th>Grupo</th>
                            <th class="text-end">Saldo</th>
                            <th class="text-end">Valor estoque</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
        }

        return `<h6 class="bi-audit-section-title">Itens de nota (itemnota)</h6>
            <div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table">
                <thead class="table-secondary">
                    <tr>
                        <th>Nota</th>
                        <th>Cód. item</th>
                        <th>Data</th>
                        <th>Grupo</th>
                        <th>Item</th>
                        <th>VED</th>
                        <th>Placa</th>
                        <th class="text-end">Valor</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderResumo(resumo) {
        if (!resumo || !resumo.length) return "";
        const rows = resumo
            .map(
                (r, i) => `<tr class="${i === resumo.length - 1 ? "fw-bold" : ""}">
                    <td>${r.label}</td>
                    <td class="text-end">${r.label.includes("%") ? Number(r.valor).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%" : fmtMoeda(r.valor)}</td>
                </tr>`
            )
            .join("");
        return `<table class="table table-sm table-bordered mb-3">
            <tbody>${rows}</tbody>
        </table>`;
    }

    function countLabel(data) {
        const parts = [];
        if (data.qtd_ctes) parts.push(`${data.qtd_ctes} CT-e(s)`);
        if (data.qtd_notas) parts.push(`${data.qtd_notas} lançamento(s)`);
        return parts.length ? `(${parts.join(" · ")})` : "";
    }

    function openBiAudit(metric) {
        const modal = document.getElementById("biAuditModal");
        const body = document.getElementById("bi-audit-body");
        if (!modal || !body) return;

        body.innerHTML = '<p class="text-center text-muted py-3">Carregando auditoria…</p>';
        modal.style.display = "block";

        const params = getPageParams();
        params.set("metric", metric);

        fetch(`/api/bi_audit?${params.toString()}`)
            .then((r) => (r.ok ? r.json() : r.json().then((e) => Promise.reject(e.error || "Erro"))))
            .then((data) => {
                if (data.error) {
                    body.innerHTML = `<p class="text-danger text-center">${data.error}</p>`;
                    return;
                }
                const filtrosTxt = [
                    data.filtros?.start_date && data.filtros?.end_date
                        ? `${data.filtros.start_date} → ${data.filtros.end_date}`
                        : "",
                    data.filtros?.placa && data.filtros.placa !== "Todos" ? `Placa: ${data.filtros.placa}` : "",
                ]
                    .filter(Boolean)
                    .join(" · ");

                const cteHtml = renderTableCte(data.linhas, data.metric);
                const notaHtml = renderTableNotas(data.linhas_notas, data.metric);
                const emptyMsg =
                    !cteHtml && !notaHtml && (!data.resumo || !data.resumo.length)
                        ? '<p class="bi-audit-empty">Nenhum lançamento encontrado para os filtros atuais.</p>'
                        : "";

                body.innerHTML = `
                    <p class="bi-audit-formula">${data.formula}</p>
                    ${filtrosTxt ? `<p class="bi-audit-filtros small text-muted">${filtrosTxt}</p>` : ""}
                    ${renderResumo(data.resumo)}
                    <div class="bi-audit-total">
                        <span>Total calculado</span>
                        <strong>${data.metric === "margem_frete" ? Number(data.total_calculado).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%" : fmtMoeda(data.total_calculado)}</strong>
                        <span class="small text-muted">${countLabel(data)}</span>
                    </div>
                    ${cteHtml}
                    ${notaHtml}
                    ${emptyMsg}
                `;
                const titleEl = modal.querySelector("#bi-audit-title");
                if (titleEl) titleEl.textContent = data.titulo;
            })
            .catch((err) => {
                body.innerHTML = `<p class="text-danger text-center">Erro ao carregar: ${err}</p>`;
            });
    }

    function closeBiAuditModal() {
        const modal = document.getElementById("biAuditModal");
        if (modal) modal.style.display = "none";
    }

    function bindBiAuditModal() {
        const modal = document.getElementById("biAuditModal");
        if (!modal || modal.dataset.auditBound === "1") return;
        modal.dataset.auditBound = "1";
        const closeBtn = modal.querySelector(".close-button");
        if (closeBtn) {
            closeBtn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                closeBiAuditModal();
            });
        }
        modal.addEventListener("click", (e) => {
            if (e.target === modal) closeBiAuditModal();
        });
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && modal.style.display === "block") closeBiAuditModal();
        });
    }

    bindBiAuditModal();

    document.addEventListener("click", function (event) {
        const auditBtn = event.target.closest(".audit-btn, .audit-btn-mini, .audit-chart-pill");
        if (auditBtn) {
            event.preventDefault();
            event.stopPropagation();
            const metric = auditBtn.dataset.auditMetric;
            if (metric) openBiAudit(metric);
            return;
        }

        const relBtn = event.target.closest(".bi-audit-rel-btn");
        if (relBtn && relBtn.dataset.numero) {
            event.preventDefault();
            const numero = relBtn.dataset.numero;
            if (typeof window.BIWEB_openRelatorioViagem === "function") {
                window.BIWEB_openRelatorioViagem(numero);
            } else {
                window.open("/api/relatorio_viagem/" + encodeURIComponent(numero), "_blank");
            }
        }
    });

    window.BIWEB_openBiAudit = openBiAudit;

    const DASHBOARD_CHART_METRICS = {
        Receita: "receita_frete",
        "Custo de viagem": "custo_viagem",
        "Despesa geral": "despesas_gerais",
        "Despesa tipo D": "despesas_tipo_d",
    };

    const DEFAULT_CHART_AUDIT_PILLS = [
        { label: "Receita", metric: "receita_frete", pill: "receita" },
        { label: "Custo viagem", metric: "custo_viagem", pill: "custo" },
        { label: "Despesa geral", metric: "despesas_gerais", pill: "geral" },
        { label: "Tipo D", metric: "despesas_tipo_d", pill: "tipod" },
    ];

    const PAGE_CHART_AUDIT_PILLS = {
        gestao: {
            default: [
                { label: "Receita CT-e", metric: "receita_frete", pill: "receita" },
                { label: "Custos operacionais", metric: "custo_operacional", pill: "custo" },
            ],
            "7": [
                { label: "Receita comércio", metric: "receita_comercio", pill: "receita" },
                { label: "Despesa comércio", metric: "despesa_comercio", pill: "geral" },
            ],
        },
        vbi: {
            financeira: {
                "1": [{ label: "A receber", metric: "contas_receber", pill: "receita" }],
                "4": [{ label: "A pagar", metric: "contas_pagar", pill: "geral" }],
                default: [
                    { label: "A receber", metric: "contas_receber", pill: "receita" },
                    { label: "A pagar", metric: "contas_pagar", pill: "geral" },
                ],
            },
            custos: {
                default: [
                    { label: "Custo viagem", metric: "custo_viagem", pill: "custo" },
                    { label: "Despesas gerais", metric: "despesas_gerais", pill: "geral" },
                    { label: "Tipo D", metric: "despesas_tipo_d", pill: "tipod" },
                ],
            },
            frota: {
                default: [
                    { label: "Custo viagem", metric: "custo_viagem", pill: "custo" },
                    { label: "Custos operacionais", metric: "custo_operacional", pill: "custo" },
                ],
            },
            default: {
                default: [
                    { label: "Receita", metric: "receita_frete", pill: "receita" },
                    { label: "Custos", metric: "custo_operacional", pill: "custo" },
                ],
            },
        },
    };

    function renderChartAuditPills(containerId, pills) {
        const el = document.getElementById(containerId);
        if (!el || !pills || !pills.length) return;
        el.innerHTML = pills
            .map(
                (p) =>
                    `<button type="button" class="chart-pill audit-chart-pill ${p.pill || ""}" data-audit-metric="${p.metric}" title="Auditar: ${p.label}"><span class="audit-chart-icon">⊕</span>${p.label}</button>`
            )
            .join("");
    }

    function resolveChartAuditPills(page, visaoKey, analiseId, fromApi) {
        if (fromApi && fromApi.length) return fromApi;
        if (page === "gestao") {
            const g = PAGE_CHART_AUDIT_PILLS.gestao;
            return g[String(analiseId)] || g.default;
        }
        if (page === "vbi") {
            const v = PAGE_CHART_AUDIT_PILLS.vbi[visaoKey] || PAGE_CHART_AUDIT_PILLS.vbi.default;
            return v[String(analiseId)] || v.default;
        }
        return DEFAULT_CHART_AUDIT_PILLS;
    }

    function bindChartSegmentAudit(chart, labelToMetric) {
        if (!chart || !chart.canvas || !labelToMetric) return;
        chart.options.onClick = (evt, elements) => {
            if (!elements || !elements.length) return;
            const ds = chart.data.datasets[elements[0].datasetIndex];
            const metric = labelToMetric[ds.label];
            if (metric) openBiAudit(metric);
        };
        chart.options.onHover = (evt, elements) => {
            chart.canvas.style.cursor = elements && elements.length ? "pointer" : "default";
        };
        chart.update();
    }

    window.BIWEB_renderChartAuditPills = renderChartAuditPills;
    window.BIWEB_resolveChartAuditPills = resolveChartAuditPills;
    window.BIWEB_bindChartSegmentAudit = bindChartSegmentAudit;
    window.BIWEB_DASHBOARD_CHART_METRICS = DASHBOARD_CHART_METRICS;
})();
