// Dentro de static/js/main.js

document.addEventListener('DOMContentLoaded', function () {
    const ctx = document.getElementById('myChart');
    if (!ctx) return;

    const urlParams = new URLSearchParams(window.location.search);
    // ===== ESTA É A LINHA DA CORREÇÃO PRINCIPAL =====
    const apiUrl = `/api/data?${urlParams.toString()}`;
    // =================================================

    fetch(apiUrl)
       .then(response => {
            if (!response.ok) {
                // Se der 404 ou outro erro, o problema fica claro no console
                throw new Error(`Erro na API: ${response.statusText}`);
            }
            return response.json();
        })
       .then(data => {
            if (!data || data.length === 0) {
                console.warn("Gráfico não renderizado: Nenhum dado recebido da API.");
                ctx.parentElement.innerHTML = '<p style="text-align:center; padding-top: 50px;">Sem dados para exibir no período selecionado.</p>';
                return;
            }

            // Lógica que usa as chaves 'label' e 'value' já corrigidas no app.py
            const labels = data.map(row => row.label);
            const values = data.map(row => row.value);

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Faturamento por Dia',
                        data: values,
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return 'R$ ' + value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                                }
                            }
                        }
                    },
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        })
       .catch(error => {
            console.error('Erro ao buscar dados para o gráfico:', error);
        });
});