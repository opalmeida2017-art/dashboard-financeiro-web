document.addEventListener("DOMContentLoaded", function () {
  const page = document.getElementById("vbi-analise-page");
  if (!page) return;

  const visaoKey = page.dataset.visaoKey;
  const analiseId = page.dataset.analiseId;
  const params = new URLSearchParams(window.location.search);
  const BC = window.BIWEBCharts || {};
  const C = BC.colors || { receita: "#2563eb", custoViagem: "#f59e0b", success: "#10b981", danger: "#ef4444" };
  const palette = BC.palette || ["#2563eb", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#7c3aed"];
  const fmtMoeda = BC.fmtMoeda || ((v) => "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 }));
  const fmtPct = (v) => Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";

  const kpiRow = document.getElementById("vbi-kpi-row");
  const chartTitle = document.getElementById("vbi-chart-title");
  const canvas = document.getElementById("vbiMainChart");
  let chartInstance = null;

  function renderKpis(kpis) {
    if (!kpis || !kpis.length) {
      kpiRow.innerHTML = '<div class="gc-kpi-card"><span class="gc-kpi-label">Sem KPIs</span></div>';
      return;
    }
    kpiRow.innerHTML = kpis
      .map(
        (k) => `
      <div class="gc-kpi-card">
        ${k.audit_metric ? `<button type="button" class="audit-btn" data-audit-metric="${k.audit_metric}" title="Auditar ${k.label}">⊕</button>` : ""}
        <div class="gc-kpi-label">${k.label}</div>
        <div class="gc-kpi-value">${k.value}</div>
        ${k.hint ? `<div class="gc-kpi-hint">${k.hint}</div>` : ""}
      </div>`
      )
      .join("");
  }

  function barDs(label, data, color) {
    return {
      label,
      data,
      ...(BC.barStyle ? BC.barStyle(color) : { backgroundColor: color, borderRadius: 6 }),
    };
  }

  function lineDs(label, data, color) {
    return {
      label,
      data,
      ...(BC.lineStyle ? BC.lineStyle(color) : { borderColor: color, backgroundColor: "transparent", fill: false }),
      tension: 0.3,
    };
  }

  function buildChart(chart) {
    if (!chart || !canvas) return;
    if (chartInstance) chartInstance.destroy();

    const mode = chart.mode || chart.type;
    const ctx = canvas.getContext("2d");
    let config;

    if (mode === "doughnut") {
      config = {
        type: "doughnut",
        data: {
          labels: chart.labels,
          datasets: [
            {
              data: chart.datasets[0].data,
              backgroundColor: BC.doughnutBackgrounds ? BC.doughnutBackgrounds(chart.labels.length) : palette,
              borderWidth: 0,
            },
          ],
        },
        options: BC.buildFeaturedOptions ? BC.buildFeaturedOptions({ type: "doughnut" }) : { maintainAspectRatio: false },
      };
    } else if (mode === "margem_hbar") {
      const unit = chart.datasets[0].unit;
      const data = chart.datasets[0].data;
      const colors =
        unit === "percent"
          ? data.map((v) => (Number(v) < 0 ? C.danger : C.success))
          : unit === "currency"
            ? data.map((v) => (Number(v) > 0 ? C.receita : C.danger))
            : palette[0];
      const bg = Array.isArray(colors) ? colors : data.map(() => colors);
      config = {
        type: "bar",
        data: {
          labels: chart.labels,
          datasets: [{ label: chart.datasets[0].label, data, backgroundColor: bg, borderRadius: 6 }],
        },
        options: {
          ...(BC.horizontalBarOptions ? BC.horizontalBarOptions(true) : {}),
          indexAxis: "y",
          plugins: {
            ...(BC.pluginsBase ? BC.pluginsBase(true, "top") : {}),
            tooltip: {
              callbacks: {
                label(ctx) {
                  const v = ctx.parsed?.x ?? ctx.raw;
                        if (unit === "percent") return ` ${ctx.dataset.label}: ${fmtPct(v)}`;
                        if (unit === "days") return ` ${ctx.dataset.label}: ${v} dias`;
                        if (unit === "count") return ` ${ctx.dataset.label}: ${Number(v).toLocaleString("pt-BR")}`;
                        if (unit === "kg") return ` ${ctx.dataset.label}: ${Number(v).toLocaleString("pt-BR")} kg`;
                        if (unit === "currency") return ` ${ctx.dataset.label}: ${fmtMoeda(v)}`;
                  return ` ${ctx.dataset.label}: ${v}`;
                },
              },
            },
          },
          scales: {
            x: {
              beginAtZero: true,
              ticks: {
                callback: (v) =>
                  unit === "percent" ? fmtPct(v) : unit === "currency" ? fmtMoeda(v) : v,
              },
            },
            y: { grid: { display: false } },
          },
        },
      };
    } else if (mode === "receita_custo_hbar" || mode === "receita_custo_bar") {
      const horizontal = mode === "receita_custo_hbar";
      const ds = chart.datasets;
      const colors = [C.receita, C.custoViagem, C.success];
      config = {
        type: "bar",
        data: {
          labels: chart.labels,
          datasets: ds.map((d, i) => barDs(d.label, d.data, colors[i % colors.length])),
        },
        options: BC.buildFeaturedOptions
          ? BC.buildFeaturedOptions({ type: "bar", options: horizontal ? { indexAxis: "y" } : {} })
          : { maintainAspectRatio: false, indexAxis: horizontal ? "y" : "x" },
      };
    } else if (mode === "stacked_bar") {
      config = {
        type: "bar",
        data: {
          labels: chart.labels,
          datasets: chart.datasets.map((d, i) => barDs(d.label, d.data, palette[i % palette.length])),
        },
        options: BC.buildFeaturedOptions
          ? BC.buildFeaturedOptions({ type: "bar", options: { scales: { x: { stacked: true }, y: { stacked: true } } } })
          : { maintainAspectRatio: false },
      };
    } else if (mode === "stacked_multi") {
      config = {
        type: "bar",
        data: {
          labels: chart.labels,
          datasets: chart.datasets.map((ds) => ({
            label: ds.label,
            data: ds.data,
            backgroundColor: ds.color || C.receita,
            stack: "despesa",
            borderRadius: 4,
          })),
        },
        options: {
          maintainAspectRatio: false,
          plugins: BC.pluginsBase ? BC.pluginsBase(true, "top") : { legend: { position: "top" } },
          scales: {
            x: { stacked: true, grid: { display: false } },
            y: {
              stacked: true,
              beginAtZero: true,
              ticks: { callback: (v) => fmtMoeda(v) },
            },
          },
        },
      };
    } else if (mode === "fluxo_caixa" || chart.type === "line") {
      config = {
        type: "line",
        data: {
          labels: chart.labels,
          datasets: (chart.datasets || []).map((ds, i) =>
            lineDs(ds.label, ds.data, [C.success, C.danger, C.receita][i % 3] || palette[i])
          ),
        },
        options: BC.buildFeaturedOptions ? BC.buildFeaturedOptions({ type: "line" }) : { maintainAspectRatio: false },
      };
    } else if (mode === "pareto") {
      config = {
        type: "bar",
        data: {
          labels: chart.labels,
          datasets: [
            barDs(chart.datasets[0].label, chart.datasets[0].data, C.receita),
            {
              label: chart.datasets[1].label,
              data: chart.datasets[1].data,
              type: "line",
              borderColor: C.danger,
              yAxisID: "y1",
              tension: 0.3,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          plugins: BC.pluginsBase ? BC.pluginsBase(true, "top") : {},
          scales: {
            y: { beginAtZero: true, ticks: { callback: (v) => fmtMoeda(v) } },
            y1: { position: "right", max: 100, grid: { drawOnChartArea: false }, ticks: { callback: (v) => fmtPct(v) } },
          },
        },
      };
    } else {
      config = {
        type: chart.type || "bar",
        data: {
          labels: chart.labels || [],
          datasets: (chart.datasets || []).map((d, i) => barDs(d.label, d.data, palette[i % palette.length])),
        },
        options: { maintainAspectRatio: false, indexAxis: chart.indexAxis || "x" },
      };
    }

    chartInstance = new Chart(ctx, config);
    const chartMetrics = buildChartAuditMap(chart);
    if (window.BIWEB_bindChartSegmentAudit && chartMetrics) {
      window.BIWEB_bindChartSegmentAudit(chartInstance, chartMetrics);
    }
  }

  function buildChartAuditMap(chart) {
    if (!chart || !chart.datasets) return null;
    const map = {};
    (chart.datasets || []).forEach((ds) => {
      const label = (ds.label || "").toLowerCase();
      if (label.includes("tipo d")) map[ds.label] = "despesas_tipo_d";
      else if (label.includes("despesa") && label.includes("comércio")) map[ds.label] = "despesa_comercio";
      else if (label.includes("receita") && label.includes("comércio")) map[ds.label] = "receita_comercio";
      else if (label.includes("despesa") && label.includes("geral")) map[ds.label] = "despesas_gerais";
      else if (label.includes("custo") && label.includes("viagem")) map[ds.label] = "custo_viagem";
      else if (label.includes("receita") || label.includes("faturamento")) map[ds.label] = "receita_frete";
      else if (label.includes("despesa")) map[ds.label] = "despesas_gerais";
      else if (label.includes("custo")) map[ds.label] = "custo_operacional";
      else if (label.includes("pagar")) map[ds.label] = "contas_pagar";
      else if (label.includes("receber")) map[ds.label] = "contas_receber";
      else map[ds.label] = "receita_frete";
    });
    return Object.keys(map).length ? map : null;
  }

  fetch(`/api/visao_bi_data?visao=${visaoKey}&analise=${analiseId}&${params.toString()}`)
    .then((r) => {
      if (!r.ok) throw new Error("API " + r.status);
      return r.json();
    })
    .then((data) => {
      if (data.error) {
        kpiRow.innerHTML = `<div class="gc-kpi-card"><span class="gc-kpi-label">${data.error}</span></div>`;
        return;
      }
      renderKpis(data.kpis);
      chartTitle.textContent = data.chart_title || data.analise?.titulo || "Gráfico";
      const pills = window.BIWEB_resolveChartAuditPills
        ? window.BIWEB_resolveChartAuditPills("vbi", visaoKey, analiseId, data.audit_pills)
        : data.audit_pills;
      if (window.BIWEB_renderChartAuditPills) {
        window.BIWEB_renderChartAuditPills("vbi-chart-audit-pills", pills);
      }
      if (!data.chart) {
        chartTitle.textContent = "Sem dados para o gráfico no período";
        return;
      }
      buildChart(data.chart);
    })
    .catch((e) => {
      kpiRow.innerHTML = `<div class="gc-kpi-card"><span class="gc-kpi-label">Erro: ${e.message}</span></div>`;
    });
});
