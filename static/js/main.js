// static/js/main.js

// Espera que o DOM esteja totalmente carregado antes de executar o script
document.addEventListener('DOMContentLoaded', function () {
    // Encontra o elemento canvas no HTML
    const ctx = document.getElementById('myChart');

    // Se o elemento canvas não existir (ex: na primeira carga sem dados), não faz nada
    if (!ctx) {
        return;
    }

    // Usa a API Fetch para obter os dados do nosso endpoint Flask
    fetch('/api/data')
       .then(response => {
            // Verifica se a resposta da API foi bem-sucedida
            if (!response.ok) {
                throw new Error('A resposta da rede não foi ok');
            }
            return response.json(); // Converte a resposta para JSON
        })
       .then(data => {
// Se não houver dados ou houver um erro, não faz nada
if (!data || data.length === 0 || data.error) {
    console.log("Nenhum dado recebido da API.");
    return;
}

            // Extrai os rótulos (labels) e os valores dos dados para o gráfico
            // Assumimos que a primeira coluna é o rótulo (eixo X)
            const labels = data.map(row => row[Object.keys(row)]);
            
            // Tenta encontrar a primeira coluna numérica para ser o valor (eixo Y)
            let valueKey = null;
            for (const key in data) {
                if (typeof data[key] === 'number') {
                    valueKey = key;
                    break;
                }
            }

            if (!valueKey) {
                console.error("Nenhuma coluna numérica encontrada para o gráfico.");
                return;
            }

            const values = data.map(row => row[valueKey]);

            // Cria um novo gráfico usando a biblioteca Chart.js
            new Chart(ctx, {
                type: 'bar', // Tipo de gráfico (barra, linha, etc.)
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Valores',
                        data: values,
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    },
                    responsive: true,
                    maintainAspectRatio: true
                }
            });
        })
       .catch(error => {
            console.error('Erro ao buscar ou processar dados para o gráfico:', error);
        });
});