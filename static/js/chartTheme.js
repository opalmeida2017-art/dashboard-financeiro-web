/**
 * BIWEB — tema visual unificado para Chart.js
 */
(function (global) {
    const font = "'Plus Jakarta Sans', system-ui, sans-serif";

    const colors = {
        receita: '#2563eb',
        receitaSoft: 'rgba(37, 99, 235, 0.12)',
        custoViagem: '#f59e0b',
        despesaGeral: '#ef4444',
        tipoD: '#7c3aed',
        teal: '#0d9488',
        slate: '#475569',
        grid: '#e2e8f0',
        text: '#64748b',
    };

    const palette = [
        '#2563eb', '#0ea5e9', '#06b6d4', '#10b981',
        '#f59e0b', '#ef4444', '#7c3aed', '#64748b',
        '#ec4899', '#14b8a6',
    ];

    function fmtMoeda(v) {
        return 'R$ ' + Number(v || 0).toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function fmtCompact(v) {
        const n = Number(v || 0);
        if (Math.abs(n) >= 1e6) return 'R$ ' + (n / 1e6).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' mi';
        if (Math.abs(n) >= 1e3) return 'R$ ' + (n / 1e3).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' mil';
        return fmtMoeda(n);
    }

    function applyDefaults() {
        if (typeof Chart === 'undefined') return;
        Chart.defaults.font.family = font;
        Chart.defaults.color = colors.text;
        Chart.defaults.borderColor = colors.grid;
    }

    function doughnutBackgrounds(n) {
        return Array.from({ length: n }, (_, i) => palette[i % palette.length]);
    }

    function gridScales(opts = {}) {
        const { yCallback, xMaxTicks, stacked = false } = opts;
        return {
            x: {
                stacked,
                grid: { display: false },
                border: { display: false },
                ticks: {
                    font: { size: 11, weight: '500' },
                    maxRotation: 40,
                    autoSkip: true,
                    maxTicksLimit: xMaxTicks || 12,
                },
            },
            y: {
                stacked,
                beginAtZero: true,
                grid: { color: colors.grid, drawBorder: false },
                border: { display: false },
                ticks: {
                    font: { size: 11 },
                    callback: yCallback || (v => fmtCompact(v)),
                    padding: 8,
                },
            },
        };
    }

    function pluginsBase(showLegend = true, position = 'bottom') {
        return {
            legend: {
                display: showLegend,
                position,
                labels: {
                    usePointStyle: true,
                    pointStyle: 'rectRounded',
                    padding: 16,
                    font: { size: 12, weight: '600' },
                },
            },
            tooltip: {
                backgroundColor: '#0f172a',
                titleFont: { size: 13, weight: '700', family: font },
                bodyFont: { size: 12, family: font },
                padding: 12,
                cornerRadius: 8,
                callbacks: {
                    label(ctx) {
                        const parsed = ctx.parsed;
                        const val = typeof parsed === 'number'
                            ? parsed
                            : (parsed?.y ?? parsed?.x ?? ctx.raw);
                        const name = ctx.dataset.label || ctx.label || '';
                        const prefix = name ? `${name}: ` : '';
                        const isKg = (ctx.dataset.label || '').toLowerCase().includes('kg');
                        const formatted = isKg
                            ? Number(val || 0).toLocaleString('pt-BR') + ' kg'
                            : fmtMoeda(val);
                        return ` ${prefix}${formatted}`;
                    },
                },
            },
        };
    }

    function barStyle(color, stack) {
        return {
            backgroundColor: color,
            borderRadius: 6,
            borderSkipped: false,
            maxBarThickness: 48,
            ...(stack ? { stack } : {}),
        };
    }

    function lineStyle(color, fill = false) {
        return {
            borderColor: color,
            backgroundColor: fill ? color.replace(')', ', 0.08)').replace('rgb', 'rgba') : 'transparent',
            borderWidth: 2.5,
            pointRadius: 4,
            pointHoverRadius: 6,
            pointBackgroundColor: '#fff',
            pointBorderWidth: 2,
            tension: 0.35,
            fill,
        };
    }

    function mainDashboardOptions(labelCount) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                ...pluginsBase(true, 'bottom'),
                legend: {
                    ...pluginsBase(true).legend,
                    labels: {
                        ...pluginsBase(true).legend.labels,
                        generateLabels(chart) {
                            return Chart.defaults.plugins.legend.labels.generateLabels(chart).map(l => ({
                                ...l,
                                fillStyle: l.strokeStyle,
                            }));
                        },
                    },
                },
            },
            scales: gridScales({
                stacked: true,
                xMaxTicks: labelCount > 18 ? 14 : undefined,
                yCallback: v => fmtCompact(v),
            }),
        };
    }

    function thumbnailOptions(extra = {}) {
        return {
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: {
                x: { display: false },
                y: { display: false },
            },
            ...extra,
        };
    }

    function featuredOptions(baseOptions = {}) {
        return {
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: pluginsBase(true, 'top'),
            ...baseOptions,
            plugins: {
                ...pluginsBase(true, 'top'),
                ...(baseOptions.plugins || {}),
            },
        };
    }

    function horizontalBarOptions(showLegend = false) {
        return {
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: pluginsBase(showLegend),
            scales: {
                x: {
                    beginAtZero: true,
                    grid: { color: colors.grid, drawBorder: false },
                    border: { display: false },
                    ticks: { callback: v => fmtCompact(v), font: { size: 11 } },
                },
                y: {
                    grid: { display: false },
                    border: { display: false },
                    ticks: { font: { size: 11, weight: '500' } },
                },
            },
        };
    }

    function doughnutOptions(showLegend = true) {
        return {
            maintainAspectRatio: false,
            cutout: '62%',
            plugins: {
                ...pluginsBase(showLegend, 'right'),
                legend: {
                    ...pluginsBase(showLegend).legend,
                    position: 'right',
                    labels: { ...pluginsBase().legend.labels, boxWidth: 12, font: { size: 11 } },
                },
            },
        };
    }

    function lineChartOptions() {
        return {
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: pluginsBase(true, 'top'),
            scales: gridScales({ yCallback: v => fmtCompact(v) }),
        };
    }

    function stackedBarOptions() {
        return {
            maintainAspectRatio: false,
            plugins: pluginsBase(true, 'top'),
            scales: gridScales({ stacked: true, yCallback: v => fmtCompact(v) }),
        };
    }

    function buildFeaturedOptions(config) {
        const plugins = { ...pluginsBase(true, 'top'), ...(config.options?.plugins || {}) };
        const { plugins: _p, ...restOptions } = config.options || {};

        if (config.type === 'doughnut') {
            return { ...doughnutOptions(true), ...restOptions, plugins: { ...doughnutOptions(true).plugins, ...plugins } };
        }
        if (config.type === 'line') {
            return { ...lineChartOptions(), ...restOptions, plugins: { ...lineChartOptions().plugins, ...plugins } };
        }
        if (config.options?.scales?.x?.stacked) {
            return { ...stackedBarOptions(), ...restOptions, plugins: { ...stackedBarOptions().plugins, ...plugins } };
        }
        if (config.options?.indexAxis === 'y') {
            return { ...horizontalBarOptions(true), ...restOptions, plugins: { ...horizontalBarOptions(true).plugins, ...plugins } };
        }
        return {
            maintainAspectRatio: false,
            plugins,
            scales: gridScales({ yCallback: v => fmtCompact(v) }),
            ...restOptions,
        };
    }

    applyDefaults();

    global.BIWEBCharts = {
        colors,
        palette,
        fmtMoeda,
        fmtCompact,
        doughnutBackgrounds,
        gridScales,
        pluginsBase,
        barStyle,
        lineStyle,
        mainDashboardOptions,
        thumbnailOptions,
        featuredOptions,
        horizontalBarOptions,
        doughnutOptions,
        lineChartOptions,
        stackedBarOptions,
        buildFeaturedOptions,
        applyDefaults,
    };
})(window);
