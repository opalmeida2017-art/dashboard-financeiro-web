document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('.fluxo-page .dash-filters form');
    const busca = document.getElementById('busca_placa');
    if (form && busca) {
        form.addEventListener('submit', function (e) {
            const placa = (busca.value || '').trim().toUpperCase();
            if (placa) {
                e.preventDefault();
                const start = document.getElementById('start_date')?.value || '';
                const end = document.getElementById('end_date')?.value || '';
                const params = new URLSearchParams({ historico: '1', placa, start_date: start, end_date: end });
                window.location.href = '/fluxo_viagem?' + params.toString();
            }
        });
    }

    document.querySelectorAll('.fluxo-link-relatorio').forEach(function (el) {
        el.addEventListener('click', function (e) {
            e.preventDefault();
            const numero = this.dataset.numero;
            if (numero) {
                window.open('/api/relatorio_viagem/' + encodeURIComponent(numero), '_blank');
            }
        });
    });

    document.querySelectorAll('.flux-track').forEach(function (track, cardIndex) {
        const fill = track.querySelector('.flux-track-fill');
        const onTop = track.dataset.truckOnTop === '1';
        const truck = onTop
            ? track.querySelector('.flux-truck--on-top')
            : track.querySelector('.flux-truck--on-rail');
        const nodes = track.querySelectorAll('.flux-track-nodes .flux-node');
        const truckIndex = parseInt(track.dataset.truckIndex || '0', 10);
        if (!fill || !truck || !nodes.length) return;

        function placeTruck() {
            const idx = Math.min(Math.max(0, truckIndex), nodes.length - 1);
            const node = nodes[idx];
            const rail = track.querySelector('.flux-track-rail');
            const lane = track.querySelector('.flux-truck-lane');
            const container = onTop && lane ? lane : rail;
            if (!container || !node) return;

            const cRect = container.getBoundingClientRect();
            const nRect = node.getBoundingClientRect();
            const centerX = nRect.left + nRect.width / 2 - cRect.left;
            const pct = Math.min(100, Math.max(0, (centerX / cRect.width) * 100));
            truck.style.left = pct + '%';
            const fillPct = onTop ? pct : pct;
            fill.style.width = fillPct + '%';
        }

        const delay = 80 + cardIndex * 45;
        window.setTimeout(placeTruck, delay);
        window.addEventListener('resize', placeTruck);
    });
});
