document.addEventListener('DOMContentLoaded', function () {
    const params = new URLSearchParams(window.location.search);
    const BC = window.BIWEBCharts || {};
    const C = BC.colors || { receita: '#2563eb', custoViagem: '#f59e0b', tipoD: '#7c3aed', teal: '#0d9488', slate: '#475569' };
    const palette = BC.palette || ['#2563eb', '#0ea5e9', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#7c3aed', '#64748b'];
    const thumbOpts = BC.thumbnailOptions ? BC.thumbnailOptions() : { maintainAspectRatio: false, plugins: { legend: { display: false } } };
    const thumbHoriz = { ...thumbOpts, indexAxis: 'y' };
    const num = v => { const n = Number(v); return Number.isFinite(n) ? n : 0; };

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

    fetch(`/api/faturamento_dashboard_data?${params.toString()}`)
        .then(response => {
            if (!response.ok) throw new Error('Falha na API: ' + response.status);
            return response.json();
        })
        .then(data => {
            if (!data || Object.keys(data).length === 0) {
                document.querySelector('.dashboard-layout').innerHTML = '<h2>Não há dados para os filtros selecionados.</h2>';
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

            if (data.evolucao_faturamento_custo) {
                const config = {
                    title: 'Evolução faturamento vs. custo total',
                    type: 'line',
                    data: {
                        labels: data.evolucao_faturamento_custo.map(d => d.Periodo || d.PeriodoLabel),
                        datasets: [
                            { label: 'Faturamento', data: data.evolucao_faturamento_custo.map(d => num(d.Faturamento)), ...(BC.lineStyle ? BC.lineStyle(C.receita) : { borderColor: C.receita }) },
                            { label: 'Custo', data: data.evolucao_faturamento_custo.map(d => num(d.Custo)), ...(BC.lineStyle ? BC.lineStyle(C.custoViagem) : { borderColor: C.custoViagem }) },
                        ],
                    },
                    options: {},
                };
                chartConfigs.set('evolucao', config);
                new Chart(document.getElementById('evolucaoChart').getContext('2d'), { type: config.type, data: config.data, options: thumbOpts });
            }

            if (data.top_clientes) {
                const config = {
                    title: 'Clientes por faturamento',
                    type: 'bar',
                    data: {
                        labels: data.top_clientes.map(d => d.nomeCliente),
                        datasets: [barDs('Faturamento', data.top_clientes.map(d => num(d.freteEmpresa)), C.receita)],
                    },
                    options: { indexAxis: 'y' },
                };
                chartConfigs.set('topClientes', config);
                new Chart(document.getElementById('topClientesChart').getContext('2d'), { type: config.type, data: config.data, options: thumbHoriz });
            }

            if (data.faturamento_filial) {
                const vals = data.faturamento_filial.map(d => num(d.freteEmpresa));
                const config = {
                    title: 'Faturamento por filial',
                    type: 'doughnut',
                    data: {
                        labels: data.faturamento_filial.map(d => d.nomeFilial),
                        datasets: [doughnutDs(vals)],
                    },
                    options: {},
                };
                chartConfigs.set('fatFilial', config);
                new Chart(document.getElementById('fatFilialChart').getContext('2d'), { type: config.type, data: config.data, options: thumbOpts });
            }

            if (data.top_rotas) {
                const config = {
                    title: 'Rotas mais frequentes',
                    type: 'bar',
                    data: {
                        labels: data.top_rotas.map(d => d.rota),
                        datasets: [barDs('Nº de viagens', data.top_rotas.map(d => num(d.contagem)), C.teal)],
                    },
                    options: { indexAxis: 'y' },
                };
                chartConfigs.set('Rotas', config);
                new Chart(document.getElementById('topRotasChart').getContext('2d'), { type: config.type, data: config.data, options: thumbHoriz });
            }

            if (data.faturamento_por_mercadoria) {
                const vals = data.faturamento_por_mercadoria.map(d => num(d.faturamento));
                const config = {
                    title: 'Faturamento por tipo de mercadoria',
                    type: 'doughnut',
                    data: {
                        labels: data.faturamento_por_mercadoria.map(d => d.mercadoria),
                        datasets: [doughnutDs(vals)],
                    },
                    options: {},
                };
                chartConfigs.set('fatMercadoria', config);
                new Chart(document.getElementById('mercadoriaChart').getContext('2d'), { type: config.type, data: config.data, options: thumbOpts });
            }

            if (data.viagens_por_veiculo) {
                const config = {
                    title: 'Viagens por veículo',
                    type: 'bar',
                    data: {
                        labels: data.viagens_por_veiculo.map(d => d.placa),
                        datasets: [barDs('Nº de viagens', data.viagens_por_veiculo.map(d => num(d.contagem)), C.tipoD)],
                    },
                    options: {},
                };
                chartConfigs.set('viagensVeiculo', config);
                new Chart(document.getElementById('viagensVeiculoChart').getContext('2d'), { type: config.type, data: config.data, options: thumbOpts });
            }

            if (data.faturamento_motorista) {
                const config = {
                    title: 'Motoristas por faturamento',
                    type: 'bar',
                    data: {
                        labels: data.faturamento_motorista.map(d => d.nomeMotorista),
                        datasets: [barDs('Faturamento', data.faturamento_motorista.map(d => d.faturamento), C.custoViagem)],
                    },
                    options: { indexAxis: 'y' },
                };
                chartConfigs.set('fatMotorista', config);
                new Chart(document.getElementById('fatMotoristaChart').getContext('2d'), { type: config.type, data: config.data, options: thumbHoriz });
            }

            if (data.volume_por_rota) {
                const pesos = data.volume_por_rota.map(d => Number(d.pesoSaida ?? d.pesosaida ?? 0));
                const config = {
                    title: 'Volume de carga (kg) por rota',
                    type: 'bar',
                    data: {
                        labels: data.volume_por_rota.map(d => d.rota),
                        datasets: [barDs('Peso total (kg)', pesos, C.slate)],
                    },
                    options: {
                        scales: {
                            y: { ticks: { callback: v => Number(v).toLocaleString('pt-BR') + ' kg' } },
                        },
                    },
                };
                chartConfigs.set('volumeRota', config);
                new Chart(document.getElementById('volumeRotaChart').getContext('2d'), { type: config.type, data: config.data, options: thumbOpts });
            }

            const ordemPreferida = ['evolucao', 'topClientes', 'fatFilial', 'Rotas', 'fatMercadoria', 'viagensVeiculo', 'fatMotorista', 'volumeRota'];
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
                '<h2>Erro ao carregar gráficos de faturamento</h2><p>Verifique os filtros e tente novamente.</p>';
        });
});
