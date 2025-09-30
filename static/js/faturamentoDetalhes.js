document.addEventListener('DOMContentLoaded', function () {
    const params = new URLSearchParams(window.location.search);
    
    fetch(`/api/faturamento_dashboard_data?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (!data || Object.keys(data).length === 0) {
                document.querySelector('.dashboard-layout').innerHTML = '<h2>Não há dados para os filtros selecionados.</h2>';
                return;
            }
            
            const chartConfigs = new Map();
            let featuredChartInstance = null;
            const featuredChartCanvas = document.getElementById('featuredChart').getContext('2d');
            const featuredChartTitle = document.getElementById('featured-chart-title');

            function updateFeaturedChart(chartId) {
                if (!chartConfigs.has(chartId)) return;
                
                const config = chartConfigs.get(chartId);
                featuredChartTitle.textContent = config.title;

                if (featuredChartInstance) {
                    featuredChartInstance.destroy();
                }
                
                featuredChartInstance = new Chart(featuredChartCanvas, {
                    type: config.type,
                    data: config.data,
                    options: { ...config.options, plugins: { legend: { display: true } } }
                });
            }

            const thumbnailOptions = {
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                }
            };
            
            // Evolução Faturamento vs. Custo
            if (data.evolucao_faturamento_custo) {
                const config = {
                    title: 'Evolução Faturamento vs. Custo Total',
                    type: 'line',
                    data: {
                        labels: data.evolucao_faturamento_custo.map(d => d.Periodo),
                        datasets: [
                            { label: 'Faturamento', data: data.evolucao_faturamento_custo.map(d => d.Faturamento), borderColor: 'rgba(41, 128, 185, 1)', fill: false },
                            { label: 'Custo', data: data.evolucao_faturamento_custo.map(d => d.Custo), borderColor: '#E67E22', fill: false }
                        ]
                    },
                    options: { maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { callback: v => 'R$ ' + v.toLocaleString('pt-BR') } } } }
                };
                chartConfigs.set('evolucao', config);
                new Chart(document.getElementById('evolucaoChart').getContext('2d'), { type: config.type, data: config.data, options: thumbnailOptions });
            }

            // Top Clientes
            if (data.top_clientes) {
                const config = {
                    title: 'Clientes por Faturamento',
                    type: 'bar',
                    data: {
                        labels: data.top_clientes.map(d => d.nomeCliente),
                        datasets: [{ label: 'Faturamento', data: data.top_clientes.map(d => d.freteEmpresa), backgroundColor: 'rgba(41, 128, 185, 0.7)' }]
                    },
                    options: { maintainAspectRatio: false, indexAxis: 'y', scales: { x: { ticks: { callback: v => 'R$ ' + v.toLocaleString('pt-BR') } } } }
                };
                chartConfigs.set('topClientes', config);
                new Chart(document.getElementById('topClientesChart').getContext('2d'), { type: config.type, data: config.data, options: { ...thumbnailOptions, indexAxis: 'y' } });
            }
            
            // Faturamento por Filial
            if (data.faturamento_filial) {
                const config = {
                    title: 'Faturamento por Filial',
                    type: 'doughnut',
                    data: {
                        labels: data.faturamento_filial.map(d => d.nomeFilial),
                        datasets: [{ data: data.faturamento_filial.map(d => d.freteEmpresa) }]
                    },
                    options: { maintainAspectRatio: false }
                };
                chartConfigs.set('fatFilial', config);
                new Chart(document.getElementById('fatFilialChart').getContext('2d'), { type: config.type, data: config.data, options: thumbnailOptions });
            }
            
            // Top Rotas
            if (data.top_rotas) {
                const config = {
                    title: 'Rotas Mais Frequentes',
                    type: 'bar',
                    data: {
                        labels: data.top_rotas.map(d => d.rota),
                        datasets: [{ label: 'Nº de Viagens', data: data.top_rotas.map(d => d.contagem), backgroundColor: 'rgba(26, 188, 156, 0.7)' }]
                    },
                    options: { maintainAspectRatio: false, indexAxis: 'y' }
                };
                chartConfigs.set('Rotas', config);
                new Chart(document.getElementById('topRotasChart').getContext('2d'), { type: config.type, data: config.data, options: { ...thumbnailOptions, indexAxis: 'y' } });
            }
            
            // Faturamento por Mercadoria
            if(data.faturamento_por_mercadoria) {
                const config = {
                     title: 'Faturamento por Tipo de Mercadoria',
                     type: 'doughnut',
                     data: {
                         labels: data.faturamento_por_mercadoria.map(d => d.mercadoria),
                         datasets: [{ data: data.faturamento_por_mercadoria.map(d => d.faturamento) }]
                     },
                     options: { maintainAspectRatio: false }
                };
                chartConfigs.set('fatMercadoria', config);
                new Chart(document.getElementById('mercadoriaChart').getContext('2d'), { type: config.type, data: config.data, options: thumbnailOptions });
            }

            // Viagens por Veículo
            if(data.viagens_por_veiculo) {
                const config = {
                     title: 'Viagens por Veículo',
                     type: 'bar',
                     data: {
                         labels: data.viagens_por_veiculo.map(d => d.placa),
                         datasets: [{ label: 'Nº de Viagens', data: data.viagens_por_veiculo.map(d => d.contagem), backgroundColor: 'rgba(142, 68, 173, 0.7)' }]
                     },
                     options: { maintainAspectRatio: false }
                };
                chartConfigs.set('viagensVeiculo', config);
                new Chart(document.getElementById('viagensVeiculoChart').getContext('2d'), { type: config.type, data: config.data, options: thumbnailOptions });
            }

            // Faturamento por Motorista
            if(data.faturamento_motorista) {
                const config = {
                     title: 'Motoristas por Faturamento',
                     type: 'bar',
                     data: {
                         labels: data.faturamento_motorista.map(d => d.nomeMotorista),
                         datasets: [{ label: 'Faturamento', data: data.faturamento_motorista.map(d => d.faturamento), backgroundColor: 'rgba(243, 156, 18, 0.7)' }]
                     },
                     options: { maintainAspectRatio: false, indexAxis: 'y', scales: { x: { ticks: { callback: v => 'R$ ' + v.toLocaleString('pt-BR') } } } }
                };
                chartConfigs.set('fatMotorista', config);
                new Chart(document.getElementById('fatMotoristaChart').getContext('2d'), { type: config.type, data: config.data, options: { ...thumbnailOptions, indexAxis: 'y' } });
            }
            
            // Volume por Rota
            if(data.volume_por_rota) {
                const config = {
                     title: 'Volume de Carga (kg) por Rota',
                     type: 'bar',
                     data: {
                         labels: data.volume_por_rota.map(d => d.rota),
                         datasets: [{ label: 'Peso Total (kg)', data: data.volume_por_rota.map(d => d.pesoSaida), backgroundColor: 'rgba(52, 73, 94, 0.7)' }]
                     },
                     options: { maintainAspectRatio: false, scales: { y: { ticks: { callback: v => v.toLocaleString('pt-BR') + ' kg' } } } }
                };
                chartConfigs.set('volumeRota', config);
                new Chart(document.getElementById('volumeRotaChart').getContext('2d'), { type: config.type, data: config.data, options: thumbnailOptions });
            }

            // Mostra o primeiro gráfico em destaque e adiciona os eventos de clique
            updateFeaturedChart('evolucao');

            document.querySelectorAll('.thumbnail-item').forEach(item => {
                item.addEventListener('click', function() {
                    const chartId = this.dataset.chartId;
                    updateFeaturedChart(chartId);
                });
            });
        });
});