document.addEventListener('DOMContentLoaded', function () {
    function coletaAutomaticaPendentes() {
        const el = document.getElementById('flux-pendentes-coleta');
        if (!el || !el.textContent) return;
        let numeros = [];
        try {
            numeros = JSON.parse(el.textContent.trim());
        } catch (e) {
            return;
        }
        if (!Array.isArray(numeros) || !numeros.length) return;

        const chave = 'flux_coleta_auto_' + numeros.join(',');
        const ultima = sessionStorage.getItem(chave);
        const ultimoErro = sessionStorage.getItem(chave + '_erro');
        if (ultima && Date.now() - parseInt(ultima, 10) < 20 * 60 * 1000) {
            return;
        }
        if (ultimoErro && Date.now() - parseInt(ultimoErro, 10) < 10 * 60 * 1000) {
            return;
        }
        sessionStorage.setItem(chave, String(Date.now()));

        const banner = document.createElement('p');
        banner.className = 'fluxo-coleta-auto-banner';
        banner.textContent = 'Buscando comprovante(s) de descarga no SATI para ' + numeros.join(', ') + '…';
        const toolbar = document.querySelector('.fluxo-toolbar');
        if (toolbar) {
            toolbar.insertAdjacentElement('afterend', banner);
        }

        fetch('/api/fluxo/coletar_comprovantes_automatico', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ numeros_internos: numeros, baixar_pdfs: true }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'sucesso') {
                    banner.textContent = data.mensagem || 'Coleta iniciada. A página será atualizada.';
                    window.setTimeout(function () { window.location.reload(); }, 8000);
                } else if (data.status === 'ignorado') {
                    banner.textContent = data.mensagem || 'Nenhum CT-e pendente (arquivo já baixado ou em coleta).';
                    banner.classList.add('fluxo-coleta-auto-banner--ok');
                    window.setTimeout(function () { banner.remove(); }, 5000);
                } else {
                    banner.textContent = data.mensagem || 'Não foi possível iniciar a coleta automática.';
                    banner.classList.add('fluxo-coleta-auto-banner--erro');
                    sessionStorage.setItem(chave + '_erro', String(Date.now()));
                }
            })
            .catch(function () {
                banner.textContent = 'Erro ao iniciar coleta automática no SATI.';
                banner.classList.add('fluxo-coleta-auto-banner--erro');
                sessionStorage.setItem(chave + '_erro', String(Date.now()));
            });
    }

    coletaAutomaticaPendentes();

    const form = document.querySelector('.fluxo-page .dash-filters form');
    const busca = document.getElementById('busca_placa');
    if (form && busca) {
        form.addEventListener('submit', function (e) {
            const placa = (busca.value || '').trim().toUpperCase();
            if (placa) {
                e.preventDefault();
                const start = document.getElementById('start_date')?.value || '';
                const end = document.getElementById('end_date')?.value || '';
                const comprovante = document.getElementById('comprovante')?.value || 'todos';
                const params = new URLSearchParams({
                    historico: '1',
                    placa,
                    start_date: start,
                    end_date: end,
                    comprovante: comprovante,
                });
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

    const modal = document.getElementById('flux-modal-descarga');
    const modalBody = document.getElementById('flux-modal-descarga-body');

    function fecharModal() {
        if (!modal) return;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
    }

    function abrirModal() {
        if (!modal) return;
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
    }

    if (modal) {
        modal.querySelectorAll('[data-flux-modal-close]').forEach(function (el) {
            el.addEventListener('click', fecharModal);
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !modal.hidden) fecharModal();
        });
    }

    function escapeHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function renderComprovantes(data) {
        if (!modalBody) return;
        const itens = data.itens || [];
        if (!itens.length) {
            modalBody.innerHTML = '<p class="flux-modal-empty">' + escapeHtml(data.mensagem || 'Nenhum comprovante encontrado.') + '</p>';
            return;
        }
        let html = '';
        itens.forEach(function (item) {
            const num = item.numero_conhecimento;
            html += '<section class="flux-doc-block">';
            html += '<h3 class="flux-doc-block-title">CT-e interno ' + escapeHtml(String(num)) + '</h3>';
            if (item.nomearq) {
                html += '<p class="flux-doc-meta"><strong>Arquivo SATI:</strong> ' + escapeHtml(item.nomearq) + '</p>';
            }
            if (item.url_arquivo) {
                html += '<p class="flux-doc-meta"><a href="' + escapeHtml(item.url_arquivo) + '" target="_blank" rel="noopener">Abrir PDF ↗</a></p>';
                html += '<iframe class="flux-doc-iframe" src="' + escapeHtml(item.url_arquivo) + '" title="PDF comprovante"></iframe>';
            }
            if (item.texto_extraido) {
                html += '<h4 class="flux-doc-subtitle">Conteúdo copiado do arquivo</h4>';
                html += '<pre class="flux-doc-texto">' + escapeHtml(item.texto_extraido) + '</pre>';
            } else if (!item.tem_arquivo) {
                html += '<p class="flux-modal-empty">Arquivo ainda não baixado. Use «Buscar comprovantes no SATI» com download.</p>';
            } else {
                html += '<p class="flux-modal-empty">PDF sem texto extraível (imagem escaneada).</p>';
            }
            html += '</section>';
        });
        modalBody.innerHTML = html;
    }

    function carregarComprovantes(numeros) {
        if (!modalBody || !numeros.length) return;
        modalBody.innerHTML = '<p class="flux-modal-loading">Carregando comprovante…</p>';
        abrirModal();
        const qs = 'numeros=' + encodeURIComponent(numeros.join(','));
        fetch('/api/comprovante_descarga?' + qs)
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
            .then(function (res) {
                renderComprovantes(res.data);
            })
            .catch(function () {
                modalBody.innerHTML = '<p class="flux-modal-empty">Erro ao carregar comprovante.</p>';
            });
    }

    function parseNumeros(str) {
        return (str || '').split(/[,;\s]+/).map(function (s) { return s.trim(); }).filter(Boolean);
    }

    document.querySelectorAll('.flux-node-doc-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const numeros = parseNumeros(this.dataset.numeros);
            if (numeros.length) carregarComprovantes(numeros);
        });
    });

    function iniciarColetaSati(numeros, btn) {
        if (!numeros.length) {
            alert('Nenhum número interno de CT-e informado.');
            return;
        }
        if (!confirm('Buscar comprovante(s) ' + numeros.join(', ') + ' no Painel de Documentos do SATI?')) return;
        if (btn) btn.disabled = true;
        fetch('/iniciar-painel-documentos?baixar_pdfs=true', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ numeros_internos: numeros.map(Number) }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                alert(data.mensagem || (data.status === 'sucesso' ? 'Coleta iniciada.' : 'Erro na coleta.'));
                if (data.status === 'sucesso') {
                    window.setTimeout(function () { window.location.reload(); }, 2500);
                }
            })
            .catch(function () { alert('Erro ao iniciar coleta no SATI.'); })
            .finally(function () { if (btn) btn.disabled = false; });
    }

    const btnGlobal = document.getElementById('btn-coletar-comprovantes-fluxo');
    if (btnGlobal) {
        btnGlobal.addEventListener('click', function () {
            const nums = prompt(
                'Números internos do CT-e (conhecimento.numero), separados por vírgula:',
                ''
            );
            if (!nums || !nums.trim()) return;
            iniciarColetaSati(parseNumeros(nums), btnGlobal);
        });
    }

    document.querySelectorAll('.fluxo-btn-sati, .fluxo-btn-sati-inline').forEach(function (btn) {
        btn.addEventListener('click', function () {
            iniciarColetaSati(parseNumeros(this.dataset.numeros), this);
        });
    });

    document.querySelectorAll('.flux-track').forEach(function (track, cardIndex) {
        const fill = track.querySelector('.flux-track-fill');
        const onTop = track.dataset.truckOnTop === '1';
        const truck = onTop
            ? track.querySelector('.flux-truck--on-top')
            : track.querySelector('.flux-truck--on-rail');
        const nodes = track.querySelectorAll('.flux-track-nodes .flux-node, .flux-track-nodes .flux-node-doc-btn');
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
            fill.style.width = pct + '%';
        }

        const delay = 80 + cardIndex * 45;
        window.setTimeout(placeTruck, delay);
        window.addEventListener('resize', placeTruck);
    });
});
