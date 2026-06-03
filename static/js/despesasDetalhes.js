document.addEventListener('DOMContentLoaded', function () {
    const params = new URLSearchParams(window.location.search);
    const BC = window.BIWEBCharts || {};
    const C = BC.colors || { receita: '#2563eb', custoViagem: '#f59e0b', tipoD: '#7c3aed', teal: '#0d9488', slate: '#475569' };
    const palette = BC.palette || ['#2563eb', '#0ea5e9', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#7c3aed', '#64748b'];
    const thumbOpts = BC.thumbnailOptions ? BC.thumbnailOptions() : { maintainAspectRatio: false, plugins: { legend: { display: false } } };
    const thumbHoriz = { ...thumbOpts, indexAxis: 'y' };

    const pick = (row, ...keys) => {
        for (const k of keys) {
            if (row[k] != null) return row[k];
        }
        return null;
    };

    const barDs = (label, data, color, extra = {}) => ({
        label,
        data,
        ...(BC.barStyle ? BC.barStyle(color) : { backgroundColor: color }),
        ...extra,
    });

    const doughnutDs = (data) => ({
        data,
        backgroundColor: BC.doughnutBackgrounds ? BC.doughnutBackgrounds(data.length) : palette,
        borderWidth: 0,
    });

    const styleStackedDatasets = (datasets) =>
        datasets.map((ds, i) => ({
            ...ds,
            ...(BC.barStyle ? BC.barStyle(ds.backgroundColor || palette[i % palette.length], 'despesa') : {}),
        }));

    fetch(`/api/despesas_dashboard_data?${params.toString()}`)
        .then(response => {
            if (!response.ok) throw new Error('Falha na API: ' + response.status);
            return response.json();
        })
        .then(data => {
            if (!data || Object.keys(data).length === 0) {
                document.querySelector('.dashboard-layout').innerHTML = '<h2>Não há dados de despesas para os filtros selecionados.</h2>';
                return;
            }

            const chartConfigs = new Map();
            let featuredChartInstance = null;
            const featuredChartCanvas = document.getElementById('featuredChart').getContext('2d');
            const featuredChartTitle = document.getElementById('featured-chart-title');

            function setActiveCard(chartId) {
                document.querySelectorAll('.chart-card').forEach(el => {
                    el.classList.toggle('active', el.dataset.chartId === chartId);
                });
            }

            function updateFeaturedChart(chartId) {
                if (!chartConfigs.has(chartId)) return;
                const config = chartConfigs.get(chartId);
                featuredChartTitle.textContent = config.title;
                setActiveCard(chartId);
                if (featuredChartInstance) featuredChartInstance.destroy();
                featuredChartInstance = new Chart(featuredChartCanvas, {
                    type: config.type,
                    data: config.data,
                    options: BC.buildFeaturedOptions ? BC.buildFeaturedOptions(config) : config.options,
                });
            }

            if (data.despesas_por_filial_e_grupo && data.despesas_por_filial_e_grupo.labels) {
                const styled = styleStackedDatasets(data.despesas_por_filial_e_grupo.datasets);
                const config = {
                    title: 'Composição das despesas por filial',
                    type: 'bar',
                    data: {
                        labels: data.despesas_por_filial_e_grupo.labels,
                        datasets: styled,
                    },
                    options: { scales: { x: { stacked: true }, y: { stacked: true } } },
                };
                chartConfigs.set('composicaoFilial', config);
                new Chart(document.getElementById('despesaComposicaoFilialChart').getContext('2d'), {
                    type: config.type,
                    data: config.data,
                    options: thumbOpts,
                });
            }

            if (data.despesa_super_grupo) {
                const vals = data.despesa_super_grupo.map(d => Number(pick(d, 'vlcontabil', 'valor_calculado') || 0));
                const config = {
                    title: 'Despesas por grupo',
                    type: 'doughnut',
                    data: {
                        labels: data.despesa_super_grupo.map(d => pick(d, 'descSuperGrupoD', 'descgrupod', 'descGrupoD')),
                        datasets: [doughnutDs(vals)],
                    },
                    options: {},
                };
                chartConfigs.set('despesaGrupo', config);
                new Chart(document.getElementById('superGrupoChart').getContext('2d'), { type: config.type, data: config.data, options: thumbOpts });
            }

            if (data.despesa_filial) {
                const config = {
                    title: 'Despesas por filial',
                    type: 'bar',
                    data: {
                        labels: data.despesa_filial.map(d => pick(d, 'nomeFil', 'nomefil', 'nomefilial')),
                        datasets: [barDs('Despesa total', data.despesa_filial.map(d => Number(pick(d, 'vlcontabil', 'valor_calculado') || 0)), C.teal)],
                    },
                    options: {},
                };
                chartConfigs.set('despesaFilial', config);
                new Chart(document.getElementById('despesaFilialChart').getContext('2d'), { type: config.type, data: config.data, options: thumbOpts });
            }

            if (data.custo_manutencao_veiculo) {
                const config = {
                    title: 'Custo de manutenção por veículo',
                    type: 'bar',
                    data: {
                        labels: data.custo_manutencao_veiculo.map(d => pick(d, 'placaVeiculo', 'placaveiculo')),
                        datasets: [barDs('Manutenção', data.custo_manutencao_veiculo.map(d => Number(pick(d, 'vlcontabil', 'valor_calculado') || 0)), C.custoViagem)],
                    },
                    options: { indexAxis: 'y' },
                };
                chartConfigs.set('manutencaoVeiculo', config);
                new Chart(document.getElementById('manutencaoVeiculoChart').getContext('2d'), { type: config.type, data: config.data, options: thumbHoriz });
            }

            if (data.gastos_por_combustivel) {
                const config = {
                    title: 'Total gasto por tipo de combustível',
                    type: 'bar',
                    data: {
                        labels: data.gastos_por_combustivel.map(d => d.item),
                        datasets: [barDs('Valor gasto', data.gastos_por_combustivel.map(d => d.valor_total), C.tipoD)],
                    },
                    options: { indexAxis: 'y' },
                };
                chartConfigs.set('gastoCombustivelItem', config);
                new Chart(document.getElementById('gastosPorCombustivelChart').getContext('2d'), { type: config.type, data: config.data, options: thumbHoriz });
            }

            if (data.combustivel_por_veiculo && data.combustivel_por_veiculo.length) {
                const rows = data.combustivel_por_veiculo;
                const config = {
                    title: 'Gasto com combustível por veículo',
                    type: 'bar',
                    data: {
                        labels: rows.map(d => pick(d, 'placaVeiculo', 'placaveiculo') || '—'),
                        datasets: [barDs('Valor gasto', rows.map(d => Number(pick(d, 'valor_total', 'valorTotal') || 0)), C.slate)],
                    },
                    options: { indexAxis: 'y' },
                };
                chartConfigs.set('gastoCombustivelVeiculo', config);
                new Chart(document.getElementById('combustivelPorVeiculoChart').getContext('2d'), { type: config.type, data: config.data, options: thumbHoriz });
            }

            const ordemPreferida = ['composicaoFilial', 'despesaGrupo', 'despesaFilial', 'manutencaoVeiculo', 'gastoCombustivelItem', 'gastoCombustivelVeiculo'];
            const primeiroId = ordemPreferida.find(id => chartConfigs.has(id));
            if (primeiroId) {
                updateFeaturedChart(primeiroId);
            } else {
                featuredChartTitle.textContent = 'Nenhum gráfico disponível para os filtros atuais';
            }

            document.querySelectorAll('.chart-card').forEach(item => {
                item.addEventListener('click', () => updateFeaturedChart(item.dataset.chartId));
            });
        })
        .catch(err => {
            console.error(err);
            document.querySelector('.dashboard-layout').innerHTML =
                '<h2>Erro ao carregar gráficos de despesas</h2><p>Verifique os filtros e tente novamente.</p>';
        });
});
