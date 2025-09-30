document.addEventListener('DOMContentLoaded', function () {
    const params = new URLSearchParams(window.location.search);
    
    fetch(`/api/despesas_dashboard_data?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (!data || Object.keys(data).length === 0) {
                document.querySelector('.dashboard-layout').innerHTML = '<h2>Não há dados de despesas para os filtros selecionados.</h2>';
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
                plugins: { legend: { display: false } }
            };

            // Composição das Despesas por Filial (Barras Empilhadas)
            if (data.despesas_por_filial_e_grupo && data.despesas_por_filial_e_grupo.labels) {
                const config = {
                    title: 'Composição das Despesas por Filial',
                    type: 'bar',
                    data: {
                        labels: data.despesas_por_filial_e_grupo.labels,
                        datasets: data.despesas_por_filial_e_grupo.datasets
                    },
                    options: { maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: v => 'R$ ' + v.toLocaleString('pt-BR') } } } }
                };
                chartConfigs.set('composicaoFilial', config);
                new Chart(document.getElementById('despesaComposicaoFilialChart').getContext('2d'), { type: config.type, data: config.data, options: thumbnailOptions });
            }
            
            // Despesas por Grupo (Rosca)
            if (data.despesa_super_grupo) {
                const config = {
                    title: 'Despesas por Grupo',
                    type: 'doughnut',
                    data: {
                        labels: data.despesa_super_grupo.map(d => d.descSuperGrupoD),
                        datasets: [{ data: data.despesa_super_grupo.map(d => d.vlcontabil) }]
                    },
                    options: { maintainAspectRatio: false }
                };
                chartConfigs.set('despesaGrupo', config);
                new Chart(document.getElementById('superGrupoChart').getContext('2d'), { type: config.type, data: config.data, options: thumbnailOptions });
            }

            // Despesas por Filial (Barra)
            if (data.despesa_filial) {
                const config = {
                    title: 'Despesas por Filial',
                    type: 'bar',
                    data: {
                        labels: data.despesa_filial.map(d => d.nomeFil),
                        datasets: [{ label: 'Despesa Total', data: data.despesa_filial.map(d => d.vlcontabil), backgroundColor: 'rgba(26, 188, 156, 0.7)' }]
                    },
                    options: { maintainAspectRatio: false, scales: { y: { ticks: { callback: v => 'R$ ' + v.toLocaleString('pt-BR') } } } }
                };
                chartConfigs.set('despesaFilial', config);
                new Chart(document.getElementById('despesaFilialChart').getContext('2d'), { type: config.type, data: config.data, options: thumbnailOptions });
            }

            // Custo de Manutenção por Veículo (Barra Horizontal)
            if (data.custo_manutencao_veiculo) {
                const config = {
                    title: 'Custo de Manutenção por Veículo',
                    type: 'bar',
                    data: {
                        labels: data.custo_manutencao_veiculo.map(d => d.placaVeiculo),
                        datasets: [{ label: 'Custo de Manutenção', data: data.custo_manutencao_veiculo.map(d => d.vlcontabil), backgroundColor: 'rgba(243, 156, 18, 0.7)' }]
                    },
                    options: { maintainAspectRatio: false, indexAxis: 'y', scales: { x: { ticks: { callback: v => 'R$ ' + v.toLocaleString('pt-BR') } } } }
                };
                chartConfigs.set('manutencaoVeiculo', config);
                new Chart(document.getElementById('manutencaoVeiculoChart').getContext('2d'), { type: config.type, data: config.data, options: { ...thumbnailOptions, indexAxis: 'y' } });
            }

            // Total Gasto por Tipo de Combustível (Barra Horizontal)
            if (data.gastos_por_combustivel) {
                const config = {
                    title: 'Total Gasto por Tipo de Combustível',
                    type: 'bar',
                    data: {
                        labels: data.gastos_por_combustivel.map(d => d.item),
                        datasets: [{ label: 'Valor Gasto (R$)', data: data.gastos_por_combustivel.map(d => d.valor_total), backgroundColor: 'rgba(142, 68, 173, 0.7)' }]
                    },
                    options: { maintainAspectRatio: false, indexAxis: 'y', scales: { x: { ticks: { callback: v => 'R$ ' + v.toLocaleString('pt-BR') } } } }
                };
                chartConfigs.set('gastoCombustivelItem', config);
                new Chart(document.getElementById('gastosPorCombustivelChart').getContext('2d'), { type: config.type, data: config.data, options: { ...thumbnailOptions, indexAxis: 'y' } });
            }
            
            // Gasto com Combustível por Veículo (Barra Horizontal)
            if (data.combustivel_por_veiculo) {
                const config = {
                    title: 'Gasto com Combustível por Veículo',
                    type: 'bar',
                    data: {
                        labels: data.combustivel_por_veiculo.map(d => d.placaVeiculo),
                        datasets: [{ label: 'Valor Gasto (R$)', data: data.combustivel_por_veiculo.map(d => d.valor_total), backgroundColor: 'rgba(52, 73, 94, 0.7)' }]
                    },
                    options: { maintainAspectRatio: false, indexAxis: 'y', scales: { x: { ticks: { callback: v => 'R$ ' + v.toLocaleString('pt-BR') } } } }
                };
                chartConfigs.set('gastoCombustivelVeiculo', config);
                new Chart(document.getElementById('combustivelPorVeiculoChart').getContext('2d'), { type: config.type, data: config.data, options: { ...thumbnailOptions, indexAxis: 'y' } });
            }

            updateFeaturedChart('composicaoFilial');

            document.querySelectorAll('.thumbnail-item').forEach(item => {
                item.addEventListener('click', function() {
                    const chartId = this.dataset.chartId;
                    updateFeaturedChart(chartId);
                });
            });
        });
});