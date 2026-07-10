/**
 * Relatório de inconsistências do banco SATI (nota / itemnota).
 */
(function () {
    function fmtMoeda(v) {
        const n = Number(v);
        const safe = Number.isFinite(n) ? n : 0;
        return safe.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    }

    function fmtPeriodoBr(ini, fim, sep = " → ") {
        if (window.BIWEBCharts?.fmtPeriodoBr) {
            return window.BIWEBCharts.fmtPeriodoBr(ini, fim, sep);
        }
        return `${ini || "—"}${sep}${fim || "—"}`;
    }

    function getPageParams() {
        const params = new URLSearchParams(window.location.search);
        if (!params.get("start_date") || !params.get("end_date")) {
            const sd = document.getElementById("start_date")?.value;
            const ed = document.getElementById("end_date")?.value;
            if (sd) params.set("start_date", sd);
            if (ed) params.set("end_date", ed);
        }
        return params;
    }

    function renderTableDuplicadas(linhas) {
        if (!linhas || !linhas.length) {
            return '<p class="bi-audit-empty">Nenhuma nota duplicada encontrada.</p>';
        }
        const rows = linhas
            .map(
                (l) => `<tr>
                    <td>${l.nota || "—"}</td>
                    <td>${l.codnota != null ? l.codnota : "—"}</td>
                    <td>${l.fornecedor || "—"}</td>
                    <td>${l.datacontrole || "—"}</td>
                    <td class="text-center text-danger fw-semibold">${l.qtd_duplicadas || "—"}</td>
                </tr>`
            )
            .join("");
        return `<div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table">
                <thead class="table-secondary">
                    <tr>
                        <th>Nota</th>
                        <th>Cód. nota</th>
                        <th>Fornecedor</th>
                        <th>Data controle</th>
                        <th class="text-center">Qtd. no grupo</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderTableFrota(linhas) {
        if (!linhas || !linhas.length) {
            return '<p class="bi-audit-empty">Nenhuma nota FROTA com despesa = N encontrada.</p>';
        }
        const rows = linhas
            .map(
                (l) => `<tr>
                    <td>${l.nota || "—"}</td>
                    <td>${l.codnota != null ? l.codnota : "—"}</td>
                    <td>${l.fornecedor || "—"}</td>
                    <td>${l.datacontrole || "—"}</td>
                    <td class="text-warning fw-semibold">${l.despesa || "—"}</td>
                    <td class="text-center">${l.qtd_itens_frota != null ? l.qtd_itens_frota : "—"}</td>
                </tr>`
            )
            .join("");
        return `<div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table">
                <thead class="table-secondary">
                    <tr>
                        <th>Nota</th>
                        <th>Cód. nota</th>
                        <th>Fornecedor</th>
                        <th>Data controle</th>
                        <th>Despesa (nota)</th>
                        <th class="text-center">Itens FROTA</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderTableGrupos(linhas) {
        if (!linhas || !linhas.length) {
            return '<p class="bi-audit-empty">Nenhum item nos grupos monitorados.</p>';
        }
        const rows = linhas
            .map(
                (l) => `<tr>
                    <td>${l.nota || "—"}</td>
                    <td>${l.coditemnota != null ? l.coditemnota : "—"}</td>
                    <td>${l.fornecedor || "—"}</td>
                    <td>${l.datacontrole || "—"}</td>
                    <td>${l.grupo || "—"}</td>
                    <td class="small">${l.item || "—"}</td>
                    <td>${l.ramo || "—"}</td>
                    <td class="text-end">${fmtMoeda(l.valor)}</td>
                </tr>`
            )
            .join("");
        return `<div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table">
                <thead class="table-secondary">
                    <tr>
                        <th>Nota</th>
                        <th>Cód. item</th>
                        <th>Fornecedor</th>
                        <th>Data controle</th>
                        <th>Grupo</th>
                        <th>Item</th>
                        <th>Ramo</th>
                        <th class="text-end">Valor</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderTableCtesSemKm(linhas) {
        if (!linhas || !linhas.length) {
            return '<p class="bi-audit-empty">Nenhum CT-e sem KM inicial/final no período.</p>';
        }
        const rows = linhas
            .map(
                (l) => `<tr>
                    <td>${l.cte || "—"}</td>
                    <td>${l.data_viagem || "—"}</td>
                    <td>${l.placa || "—"}</td>
                    <td>${l.motorista || "—"}</td>
                    <td class="small">${l.cliente || "—"}</td>
                    <td class="small">${l.rota || "—"}</td>
                    <td class="text-warning fw-semibold text-center">${l.km_inicial || "—"}</td>
                    <td class="text-warning fw-semibold text-center">${l.km_final || "—"}</td>
                    <td class="text-end">${l.km_rodado != null ? Number(l.km_rodado).toLocaleString("pt-BR") : "—"}</td>
                </tr>`
            )
            .join("");
        return `<div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table">
                <thead class="table-secondary">
                    <tr>
                        <th>CT-e \\ interno</th>
                        <th>Data viagem</th>
                        <th>Placa</th>
                        <th>Motorista</th>
                        <th>Cliente</th>
                        <th>Rota</th>
                        <th class="text-center">KM ini.</th>
                        <th class="text-center">KM fim</th>
                        <th class="text-end">KM rodado</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderTableVeiculomulta(linhas) {
        if (!linhas || !linhas.length) {
            return '<p class="bi-audit-empty">Nenhuma nota de multa (veiculomulta) com despesa = N e valor descontado vazio.</p>';
        }
        const rows = linhas
            .map(
                (l) => `<tr>
                    <td>${l.codveiculomulta != null ? l.codveiculomulta : "—"}</td>
                    <td>${l.nota || "—"}</td>
                    <td>${l.codnota != null ? l.codnota : "—"}</td>
                    <td>${l.num_multa || "—"}</td>
                    <td>${l.fornecedor || "—"}</td>
                    <td>${l.datacontrole || "—"}</td>
                    <td class="text-end">${Number(l.valormulta || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}</td>
                    <td class="text-end">${Number(l.valordescontado || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}</td>
                    <td class="text-warning fw-semibold">${l.despesa || "—"}</td>
                    <td class="text-success fw-semibold">${l.despesa_esperada || "—"}</td>
                </tr>`
            )
            .join("");
        return `<div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table">
                <thead class="table-secondary">
                    <tr>
                        <th>Cód. multa</th>
                        <th>Nota</th>
                        <th>Cód. nota</th>
                        <th>Nº multa</th>
                        <th>Fornecedor</th>
                        <th>Data controle</th>
                        <th class="text-end">Valor multa</th>
                        <th class="text-end">Valor descontado</th>
                        <th>Despesa atual</th>
                        <th>Despesa esperada</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderTableCtesMesmaNota(linhas) {
        if (!linhas || !linhas.length) {
            return '<p class="bi-audit-empty">Nenhum CT-e compartilhando a mesma nota no período.</p>';
        }
        const rows = linhas
            .map(
                (l) => `<tr>
                    <td>${l.nota || "—"}</td>
                    <td class="small" title="${l.chave_completa || ""}">${l.chave || "—"}</td>
                    <td class="text-center text-danger fw-semibold">${l.qtd_ctes != null ? l.qtd_ctes : "—"}</td>
                    <td>${l.cte || "—"}</td>
                    <td>${l.data_viagem || "—"}</td>
                    <td>${l.placa || "—"}</td>
                    <td class="small">${l.cliente || "—"}</td>
                </tr>`
            )
            .join("");
        return `<div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table">
                <thead class="table-secondary">
                    <tr>
                        <th>Nota (série/nº)</th>
                        <th>Chave NFe</th>
                        <th class="text-center">Qtd CT-es</th>
                        <th>CT-e \\ interno</th>
                        <th>Data viagem</th>
                        <th>Placa</th>
                        <th>Cliente</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderSecao(secao) {
        let tableHtml = "";
        if (secao.id === "ctes_mesma_nota") {
            tableHtml = renderTableCtesMesmaNota(secao.linhas);
        } else if (secao.id === "ctes_sem_km") {
            tableHtml = renderTableCtesSemKm(secao.linhas);
        } else if (secao.id === "notas_duplicadas") {
            tableHtml = renderTableDuplicadas(secao.linhas);
        } else if (
            secao.id === "frota_despesa_n" ||
            secao.id === "frota_os_despesa_n" ||
            secao.id === "frota_sem_despesa_n"
        ) {
            tableHtml = renderTableFrota(secao.linhas);
        } else if (secao.id === "grupos_especiais") {
            tableHtml = renderTableGrupos(secao.linhas);
        } else if (secao.id === "veiculomulta_despesa") {
            tableHtml = renderTableVeiculomulta(secao.linhas);
        }
        return `<section class="audit-section bi-inconsist-secao" data-secao="${secao.id}">
            <h5>${secao.titulo} <span class="badge bg-secondary">${secao.total || 0}</span></h5>
            <p class="small text-muted mb-2">${secao.descricao || ""}</p>
            ${tableHtml}
        </section>`;
    }

    function openInconsistenciasModal() {
        const modal = document.getElementById("inconsistenciasModal");
        const body = document.getElementById("inconsistencias-body");
        if (!modal || !body) return;

        body.innerHTML = '<p class="text-center text-muted py-3">Carregando inconsistências…</p>';
        modal.style.display = "block";

        const params = getPageParams();
        fetch(`/api/inconsistencias_banco?${params.toString()}`)
            .then(async (r) => {
                const ct = (r.headers.get("content-type") || "").toLowerCase();
                if (!ct.includes("application/json")) {
                    if (r.status === 404) {
                        throw new Error("API não encontrada no servidor — é necessário atualizar o BIWEB.");
                    }
                    throw new Error(`Resposta inválida do servidor (HTTP ${r.status}).`);
                }
                const data = await r.json();
                if (!r.ok) {
                    throw new Error(data.error || `Erro HTTP ${r.status}`);
                }
                return data;
            })
            .then((data) => {
                if (data.error) {
                    body.innerHTML = `<p class="text-danger text-center">${data.error}</p>`;
                    return;
                }
                const filtrosTxt = [
                    data.filtros?.start_date && data.filtros?.end_date
                        ? `Período: ${fmtPeriodoBr(data.filtros.start_date, data.filtros.end_date)}`
                        : "",
                    data.filtros?.exclui ? `Excluídos: ${data.filtros.exclui}` : "",
                ]
                    .filter(Boolean)
                    .join(" · ");

                const secoesHtml = (data.secoes || []).map(renderSecao).join("");
                const totalGeral = data.total_geral != null ? data.total_geral : 0;

                body.innerHTML = `
                    ${filtrosTxt ? `<p class="bi-audit-filtros small text-muted">${filtrosTxt}</p>` : ""}
                    <div class="bi-audit-total mb-3">
                        <span>Total de registros listados</span>
                        <strong>${totalGeral}</strong>
                    </div>
                    ${secoesHtml || '<p class="bi-audit-empty">Nenhuma inconsistência encontrada.</p>'}
                `;
                const titleEl = modal.querySelector("#inconsistencias-title");
                if (titleEl) titleEl.textContent = data.titulo || "Inconsistências do banco";
            })
            .catch((err) => {
                body.innerHTML = `<p class="text-danger text-center">Erro ao carregar: ${err}</p>`;
            });
    }

    function closeInconsistenciasModal() {
        const modal = document.getElementById("inconsistenciasModal");
        if (modal) modal.style.display = "none";
    }

    function bindInconsistenciasModal() {
        const modal = document.getElementById("inconsistenciasModal");
        if (!modal || modal.dataset.bound === "1") return;
        modal.dataset.bound = "1";

        const closeBtn = modal.querySelector(".close-button");
        if (closeBtn) {
            closeBtn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                closeInconsistenciasModal();
            });
        }
        modal.addEventListener("click", (e) => {
            if (e.target === modal) closeInconsistenciasModal();
        });
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && modal.style.display === "block") closeInconsistenciasModal();
        });
        const printBtn = modal.querySelector("[data-print-inconsistencias]");
        if (printBtn) {
            printBtn.addEventListener("click", (e) => {
                e.preventDefault();
                document.body.classList.add("bi-inconsist-print-mode");
                window.print();
                window.setTimeout(function () {
                    document.body.classList.remove("bi-inconsist-print-mode");
                }, 400);
            });
        }
    }

    bindInconsistenciasModal();

    document.addEventListener("click", function (event) {
        const btn = event.target.closest("#btn-inconsistencias-banco");
        if (!btn) return;
        event.preventDefault();
        event.stopPropagation();
        openInconsistenciasModal();
    });

    window.BIWEB_openInconsistencias = openInconsistenciasModal;
})();
