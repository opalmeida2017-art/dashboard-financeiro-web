document.addEventListener("DOMContentLoaded", function () {
  const page = document.getElementById("gc-analise-page");
  if (!page) return;

  const analiseId = page.dataset.analiseId;
  const params = new URLSearchParams(window.location.search);
  const BC = window.BIWEBCharts || {};
  const C = BC.colors || {
    receita: "#2563eb",
    custoViagem: "#f59e0b",
    success: "#10b981",
    danger: "#ef4444",
  };
  const palette = BC.palette || ["#2563eb", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#7c3aed"];
  const fmtMoeda = BC.fmtMoeda || ((v) => "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 }));
  const fmtPct = (v) => Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";

  const kpiRow = document.getElementById("gc-kpi-row");
  const chartTitle = document.getElementById("gc-chart-title");
  const canvas = document.getElementById("gcMainChart");
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

  function tooltipForUnit(unit) {
    if (unit === "percent") {
      return {
        callbacks: {
          label(ctx) {
            const v = ctx.parsed?.x ?? ctx.parsed?.y ?? ctx.raw;
            return ` ${ctx.dataset.label}: ${fmtPct(v)}`;
          },
        },
      };
    }
    return {};
  }

  function buildChart(chart) {
    if (!chart || !canvas) return;
    if (chartInstance) chartInstance.destroy();

    const mode = chart.mode || chart.type;
    const ctx = canvas.getContext("2d");
    let config;

    if (mode === "margem_hbar") {
      const data = chart.datasets[0].data;
      const colors = data.map((v) => (Number(v) < 0 ? C.danger : C.success));
      config = {
        type: "bar",
        data: {
          labels: chart.labels,
          datasets: [
            {
              label: chart.datasets[0].label,
              data,
              backgroundColor: colors,
              borderRadius: 6,
              maxBarThickness: 36,
            },
          ],
        },
        options: {
          ...(BC.horizontalBarOptions ? BC.horizontalBarOptions(true) : {}),
          indexAxis: "y",
          plugins: {
            ...(BC.pluginsBase ? BC.pluginsBase(true, "top") : {}),
            tooltip: tooltipForUnit("percent"),
          },
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: "#e2e8f0" },
              ticks: { callback: (v) => fmtPct(v) },
            },
            y: { grid: { display: false } },
          },
        },
      };
    } else if (mode === "receita_custo_hbar" || mode === "receita_custo_bar") {
      const horizontal = mode === "receita_custo_hbar";
      config = {
        type: "bar",
        data: {
          labels: chart.labels,
          datasets: [
            barDs(chart.datasets[0].label, chart.datasets[0].data, C.receita),
            barDs(chart.datasets[1].label, chart.datasets[1].data, C.custoViagem),
          ],
        },
        options: BC.buildFeaturedOptions
          ? BC.buildFeaturedOptions({
              type: "bar",
              options: horizontal ? { indexAxis: "y" } : {},
            })
          : {
              responsive: true,
              maintainAspectRatio: false,
              indexAxis: horizontal ? "y" : "x",
              plugins: { legend: { position: "top" } },
            },
      };
    } else if (mode === "line_ticket" || chart.type === "line") {
      config = {
        type: "line",
        data: {
          labels: chart.labels,
          datasets: (chart.datasets || []).map((ds, i) =>
            lineDs(ds.label, ds.data, palette[i % palette.length])
          ),
        },
        options: BC.buildFeaturedOptions
          ? BC.buildFeaturedOptions({ type: "line" })
          : { responsive: true, maintainAspectRatio: false },
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
              backgroundColor: "transparent",
              yAxisID: "y1",
              tension: 0.3,
              pointRadius: 4,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: BC.pluginsBase ? BC.pluginsBase(true, "top") : { legend: { position: "top" } },
          scales: {
            x: { grid: { display: false } },
            y: {
              beginAtZero: true,
              position: "left",
              ticks: { callback: (v) => BC.fmtCompact ? BC.fmtCompact(v) : fmtMoeda(v) },
            },
            y1: {
              beginAtZero: true,
              position: "right",
              max: 100,
              grid: { drawOnChartArea: false },
              ticks: { callback: (v) => fmtPct(v) },
            },
          },
        },
      };
    } else if (mode === "spread_hbar") {
      const data = chart.datasets[0].data;
      const colors = data.map((v) => (Number(v) < 0 ? C.danger : C.receita));
      config = {
        type: "bar",
        data: {
          labels: chart.labels,
          datasets: [{ label: chart.datasets[0].label, data, backgroundColor: colors, borderRadius: 6 }],
        },
        options: BC.buildFeaturedOptions
          ? BC.buildFeaturedOptions({ type: "bar", options: { indexAxis: "y" } })
          : { maintainAspectRatio: false, indexAxis: "y" },
      };
    } else {
      config = {
        type: chart.type || "bar",
        data: {
          labels: chart.labels || [],
          datasets: (chart.datasets || []).map((ds, i) =>
            barDs(ds.label, ds.data, palette[i % palette.length])
          ),
        },
        options: BC.buildFeaturedOptions
          ? BC.buildFeaturedOptions({ type: chart.type, indexAxis: chart.indexAxis })
          : { maintainAspectRatio: false, indexAxis: chart.indexAxis || "x" },
      };
    }

    chartInstance = new Chart(ctx, config);
  }

  fetch(`/api/gestao_comercial_data?analise=${analiseId}&${params.toString()}`)
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
