/**
 * Análise geral da margem — modal com fechamento, CT-e, notas e custos.
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

    function fmtValor(linha) {
        if (linha.pct) {
            const n = Number(linha.valor);
            return `${Number.isFinite(n) ? n.toFixed(2) : "0,00"}%`;
        }
        if (linha.texto) {
            return String(linha.valor != null ? linha.valor : "—");
        }
        return fmtMoeda(linha.valor);
    }

    function getPageParams() {
        const params = new URLSearchParams(window.location.search);
        if (!params.get("start_date") || !params.get("end_date")) {
            const sd = document.getElementById("start_date")?.value;
            const ed = document.getElementById("end_date")?.value;
            if (sd) params.set("start_date", sd);
            if (ed) params.set("end_date", ed);
        }
        ["placa", "filial", "tipo_negocio", "unidade_embarque", "embarcador"].forEach((key) => {
            const el = document.getElementById(`${key}_filter`);
            if (el && el.value) params.set(key, el.value);
        });
        return params;
    }

    function renderLinhas(linhas) {
        if (!linhas || !linhas.length) return '<p class="bi-audit-empty">Sem dados.</p>';
        const rows = linhas
            .map((l) => {
                const cls = l.destaque ? "fw-semibold" : "";
                const info = l.info ? ` <span class="small text-muted">(${l.info})</span>` : "";
                return `<tr class="${cls}"><td>${l.label}${info}</td><td class="text-end">${fmtValor(l)}</td></tr>`;
            })
            .join("");
        return `<div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table"><tbody>${rows}</tbody></table></div>`;
    }

    function renderVerificacoes(itens) {
        if (!itens || !itens.length) return "";
        const rows = itens
            .map(
                (v) => `<tr>
                    <td class="bi-margem-verif-label">${v.verificacao || "—"}</td>
                    <td>${v.resultado || "—"}</td>
                </tr>`
            )
            .join("");
        return `<div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table bi-margem-verif-table">
                <thead class="table-secondary">
                    <tr><th>Verificação</th><th>Resultado</th></tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderGrupos(grupos) {
        if (!grupos || !grupos.length) return '<p class="bi-audit-empty">Nenhum grupo no período.</p>';
        const rows = grupos
            .map(
                (g) => `<tr>
                    <td>${g.grupo || "—"}</td>
                    <td class="text-end">${fmtMoeda(g.valor)}</td>
                    <td class="text-end">${g.pct_despesas != null ? `${Number(g.pct_despesas).toFixed(1)}%` : "—"}</td>
                </tr>`
            )
            .join("");
        return `<table class="table table-sm table-bordered bi-audit-table">
            <thead class="table-secondary">
                <tr><th>Grupo</th><th class="text-end">Valor</th><th class="text-end">% desp.</th></tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>`;
    }

    function renderComponentesPrev(comp) {
        if (!comp || !comp.length) return '<p class="bi-audit-empty">Sem custo prévia no período.</p>';
        const rows = comp
            .map((c) => {
                const cls = c.destaque ? "fw-semibold table-warning" : "";
                return `<tr class="${cls}"><td>${c.componente || "—"}</td><td class="text-end">${fmtMoeda(c.valor)}</td></tr>`;
            })
            .join("");
        return `<table class="table table-sm table-bordered bi-audit-table">
            <thead class="table-secondary">
                <tr><th>Componente</th><th class="text-end">Custo prévia</th></tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>`;
    }

    function renderQuadroPrevia(quadro) {
        if (!quadro) return "";
        return `<div class="bi-margem-quadro-previa">
            <h6 class="bi-margem-quadro-title">${quadro.titulo || "Custo prévia CT-e"}</h6>
            ${renderComponentesPrev(quadro.componentes)}
            ${quadro.comentario ? `<p class="bi-margem-comentario small mb-0 mt-2">${quadro.comentario}</p>` : ""}
        </div>`;
    }

    function renderResumo(causas) {
        if (!causas || !causas.length) return "";
        const rows = causas
            .map((c) => {
                const cls = c.destaque ? "table-danger fw-semibold" : "";
                return `<tr class="${cls}"><td>${c.causa || "—"}</td><td>${c.impacto || "—"}</td></tr>`;
            })
            .join("");
        return `<div class="table-responsive bi-audit-table-wrap">
            <table class="table table-sm table-bordered bi-audit-table">
                <thead class="table-secondary"><tr><th>Causa</th><th>Impacto na margem</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function renderSecao(secao) {
        const coment = secao.comentario ? `<p class="bi-margem-comentario small mb-2">${secao.comentario}</p>` : "";
        const conclusao = secao.conclusao
            ? `<p class="bi-margem-conclusao small fw-semibold mb-2">${secao.conclusao}</p>`
            : "";
        let body = "";

        const tipo = secao.tipo || secao.id;
        if (tipo === "duo" || secao.id === "custo_previsto") {
            body = `<div class="bi-margem-duo-grid">
                <div class="bi-margem-duo-col"><h6 class="bi-margem-duo-title">Grupo (despesas gerais)</h6>${renderGrupos(secao.grupos)}</div>
                <div class="bi-margem-duo-col"><h6 class="bi-margem-duo-title">Custo prévia CT-e</h6>${renderComponentesPrev(secao.componentes_previsto)}</div>
            </div>`;
        } else if (tipo === "grupos" || secao.id === "peso_margem") {
            body = renderGrupos(secao.grupos);
        } else if (tipo === "verificacao_quadro" || secao.id === "cte") {
            body = `${renderVerificacoes(secao.verificacoes)}${conclusao}${renderQuadroPrevia(secao.quadro_previa)}`;
        } else if (tipo === "verificacao" || secao.id === "notas") {
            body = `${renderVerificacoes(secao.verificacoes)}${conclusao}`;
        } else if (tipo === "resumo" || secao.id === "resumo") {
            body = renderResumo(secao.causas);
        } else {
            body = renderLinhas(secao.linhas);
        }

        return `<section class="audit-section bi-margem-secao" data-secao="${secao.id}">
            <h5>${secao.titulo}</h5>
            <p class="small text-muted mb-1">${secao.descricao || ""}</p>
            ${coment}
            ${body}
        </section>`;
    }

    function alertClass(situacao) {
        if (situacao === "negativa") return "alert-danger";
        if (situacao === "positiva") return "alert-success";
        return "alert-info";
    }

    function openMargemAnaliseModal() {
        const modal = document.getElementById("margemAnaliseModal");
        const body = document.getElementById("margem-analise-body");
        if (!modal || !body) return;

        body.innerHTML = '<p class="text-center text-muted py-3">Gerando análise…</p>';
        modal.style.display = "block";

        fetch(`/api/analise_margem_geral?${getPageParams().toString()}`)
            .then(async (r) => {
                const ct = (r.headers.get("content-type") || "").toLowerCase();
                if (!ct.includes("application/json")) throw new Error(`Resposta inválida (HTTP ${r.status}).`);
                const data = await r.json();
                if (!r.ok) throw new Error(data.error || `Erro HTTP ${r.status}`);
                return data;
            })
            .then((data) => {
                if (data.error) {
                    body.innerHTML = `<p class="text-danger text-center">${data.error}</p>`;
                    return;
                }
                const fechamento = (data.secoes || []).find((s) => s.id === "fechamento");
                const semDadosPainel =
                    fechamento &&
                    (fechamento.linhas || []).every((l) => {
                        if (l.pct) return Number(l.valor) === 0;
                        if (l.texto) return true;
                        return Number(l.valor) === 0;
                    });
                const filtrosTxt = [
                    data.filtros?.start_date && data.filtros?.end_date
                        ? `Período: ${fmtPeriodoBr(data.filtros.start_date, data.filtros.end_date)}`
                        : "",
                    data.filtros?.placa ? `Placa: ${data.filtros.placa}` : "",
                ]
                    .filter(Boolean)
                    .join(" · ");

                body.innerHTML = `
                    ${filtrosTxt ? `<p class="bi-audit-filtros small text-muted">${filtrosTxt}</p>` : ""}
                    ${
                        semDadosPainel
                            ? `<div class="alert alert-warning" role="alert">
                        <strong>Período sem dados no painel.</strong>
                        Verifique o ano das datas (ex.: jun/2026). Os KPIs zerados não impedem as verificações de CT-e e notas abaixo.
                        <button type="button" class="tb-btn tb-btn-primary btn-sm ms-2" id="btn-usar-periodo-padrao-modal">Usar mês atual</button>
                    </div>`
                            : ""
                    }
                    <div class="alert ${alertClass(data.situacao)} bi-margem-resumo" role="alert">
                        <strong>Resumo:</strong> ${data.comentario_geral || ""}
                    </div>
                    ${(data.secoes || []).map(renderSecao).join("")}
                `;
                const titleEl = modal.querySelector("#margem-analise-title");
                if (titleEl) titleEl.textContent = data.titulo || "Análise geral da margem";
                body.querySelector("#btn-usar-periodo-padrao-modal")?.addEventListener("click", (e) => {
                    e.preventDefault();
                    window.location.href = window.location.pathname;
                });
            })
            .catch((err) => {
                body.innerHTML = `<p class="text-danger text-center">Erro ao carregar: ${err}</p>`;
            });
    }

    function closeMargemAnaliseModal() {
        const modal = document.getElementById("margemAnaliseModal");
        if (modal) modal.style.display = "none";
    }

    function bindMargemAnaliseModal() {
        const modal = document.getElementById("margemAnaliseModal");
        if (!modal || modal.dataset.bound === "1") return;
        modal.dataset.bound = "1";

        modal.querySelector(".close-button")?.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            closeMargemAnaliseModal();
        });
        modal.addEventListener("click", (e) => {
            if (e.target === modal) closeMargemAnaliseModal();
        });
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && modal.style.display === "block") closeMargemAnaliseModal();
        });
        modal.querySelector("[data-print-margem-analise]")?.addEventListener("click", (e) => {
            e.preventDefault();
            document.body.classList.add("bi-margem-print-mode");
            window.print();
            window.setTimeout(() => document.body.classList.remove("bi-margem-print-mode"), 400);
        });
    }

    bindMargemAnaliseModal();

    function irPeriodoPadrao() {
        window.location.href = window.location.pathname;
    }

    function bindDashEmptyActions(root) {
        const scope = root || document;
        scope.querySelector("#btn-usar-periodo-padrao")?.addEventListener("click", (e) => {
            e.preventDefault();
            irPeriodoPadrao();
        });
        scope.querySelector("#btn-analise-margem-empty")?.addEventListener("click", (e) => {
            e.preventDefault();
            openMargemAnaliseModal();
        });
    }

    window.BIWEB_bindDashEmptyActions = bindDashEmptyActions;
    bindDashEmptyActions(document);

    document.addEventListener("click", (event) => {
        const btn = event.target.closest("#btn-analise-margem-geral, #btn-analise-margem-toolbar");
        if (!btn) return;
        event.preventDefault();
        event.stopPropagation();
        openMargemAnaliseModal();
    });

    window.BIWEB_openMargemAnalise = openMargemAnaliseModal;
})();
