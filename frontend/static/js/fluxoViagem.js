document.addEventListener('DOMContentLoaded', function () {
    function diasEntre(inicio, fim) {
        if (!inicio || !fim) return 999;
        const a = new Date(inicio + 'T00:00:00');
        const b = new Date(fim + 'T00:00:00');
        return Math.round((b - a) / 86400000);
    }

    function mesVigenteParams(params) {
        const hoje = new Date();
        const ini = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
        params.set('start_date', ini.toISOString().slice(0, 10));
        params.set('end_date', hoje.toISOString().slice(0, 10));
        return params;
    }

    function fetchComRetry(url, tentativa, maxTentativas) {
        const hint = document.getElementById('fluxo-retry-hint');
        if (hint) {
            hint.textContent = tentativa > 0
                ? 'Servidor ocupado — tentativa ' + (tentativa + 1) + ' de ' + maxTentativas + '…'
                : '';
        }
        return fetch(url, { credentials: 'same-origin' }).then(function (r) {
            if ((r.status === 502 || r.status === 503 || r.status === 504) && tentativa < maxTentativas - 1) {
                const espera = Math.min(15000, 2000 * Math.pow(2, tentativa));
                return new Promise(function (res) { window.setTimeout(res, espera); })
                    .then(function () { return fetchComRetry(url, tentativa + 1, maxTentativas); });
            }
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r;
        });
    }

    function escapeAttr(s) {
        return String(s || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function atualizarDatalistPlacas(placas) {
        const dl = document.getElementById('lista-placas');
        if (!dl || !placas || !placas.length) return;
        const vistos = {};
        const opts = [];
        Array.prototype.forEach.call(dl.options || [], function (opt) {
            const placa = String(opt.value || '').trim().toUpperCase();
            const tipo = String(opt.label || '').trim();
            if (!placa || vistos[placa]) return;
            vistos[placa] = true;
            opts.push('<option value="' + escapeAttr(placa) + '"' + (tipo ? ' label="' + escapeAttr(tipo) + '"' : '') + '></option>');
        });
        placas.forEach(function (p) {
            const placa = String((p && typeof p === 'object') ? (p.placa || '') : (p || '')).trim().toUpperCase();
            const tipo = String((p && typeof p === 'object') ? (p.tipo || '') : '').trim();
            if (!placa || vistos[placa]) return;
            vistos[placa] = true;
            opts.push('<option value="' + escapeAttr(placa) + '"' + (tipo ? ' label="' + escapeAttr(tipo) + '"' : '') + '></option>');
        });
        if (!opts.length) return;
        dl.innerHTML = opts.join('');
        dl.dataset.loaded = '1';
    }

    function carregarPlacasFluxo() {
        const dl = document.getElementById('lista-placas');
        if (!dl || dl.dataset.loaded === '1') return;
        fetch('/api/fluxo_viagem_placas', { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                atualizarDatalistPlacas(data.placas || []);
            })
            .catch(function () {
                // O fluxo principal ainda pode preencher as placas quando terminar.
            });
    }

    function coletaAutomaticaHabilitada() {
        const el = document.getElementById('flux-coleta-auto-flag');
        if (el) {
            try {
                return JSON.parse(el.textContent) === true;
            } catch (e) {
                return false;
            }
        }
        return false;
    }

    function fluxoParamsDaPagina() {
        let params = new URLSearchParams(window.location.search.replace(/^\?/, ''));
        const form = document.querySelector('.fluxo-page .dash-filters form');
        const start = document.getElementById('start_date')?.value;
        const end = document.getElementById('end_date')?.value;
        const comprovante = document.getElementById('comprovante')?.value;
        const mdfe = document.getElementById('mdfe')?.value;
        if (start) params.set('start_date', start);
        if (end) params.set('end_date', end);
        if (comprovante) params.set('comprovante', comprovante);
        if (mdfe) params.set('mdfe', mdfe);
        const hist = form?.querySelector('input[name="historico"]');
        const placaHist = form?.querySelector('input[name="placa"]');
        if (hist && hist.value) {
            params.set('historico', hist.value);
        } else {
            params.delete('historico');
        }
        if (placaHist && placaHist.value) {
            params.set('placa', placaHist.value);
        } else if (!params.get('historico')) {
            params.delete('placa');
        }
        ['filial', 'tipo_negocio', 'embarcador', 'unidade_embarque', 'busca_placa'].forEach(function (k) {
            params.delete(k);
        });
        if (!params.get('mdfe')) params.set('mdfe', 'todos');
        if (!params.get('comprovante')) params.set('comprovante', 'todos');
        return params;
    }

    function fluxoApiUrl(params) {
        return '/api/fluxo_viagem_body?' + params.toString();
    }

    function fluxoUrlComParams(params) {
        const base = (document.querySelector('.fluxo-page .dash-filters form') || {}).action
            || window.location.pathname;
        return base + '?' + params.toString();
    }

    (function setupFluxoForm() {
        const form = document.querySelector('.fluxo-page .dash-filters form');
        const busca = document.getElementById('busca_placa');
        if (form) {
            form.addEventListener('submit', function (e) {
                const placa = (busca && busca.value || '').trim().toUpperCase();
                if (placa) return;

                e.preventDefault();
                const params = new URLSearchParams();
                const start = document.getElementById('start_date')?.value || '';
                const end = document.getElementById('end_date')?.value || '';
                const comprovante = document.getElementById('comprovante')?.value || 'todos';
                const mdfe = document.getElementById('mdfe')?.value || 'todos';
                if (start) params.set('start_date', start);
                if (end) params.set('end_date', end);
                params.set('comprovante', comprovante);
                params.set('mdfe', mdfe);
                const hist = form.querySelector('input[name="historico"]');
                const placaHist = form.querySelector('input[name="placa"]');
                if (hist && hist.value) params.set('historico', hist.value);
                if (placaHist && placaHist.value) params.set('placa', placaHist.value);
                window.location.href = fluxoUrlComParams(params);
            });
        }
        if (form && busca) {
            form.addEventListener('submit', function (e) {
                const placa = (busca.value || '').trim().toUpperCase();
                if (placa) {
                    e.preventDefault();
                    const start = document.getElementById('start_date')?.value || '';
                    const end = document.getElementById('end_date')?.value || '';
                    const comprovante = document.getElementById('comprovante')?.value || 'todos';
                    const mdfe = document.getElementById('mdfe')?.value || 'todos';
                    const params = new URLSearchParams({
                        historico: '1',
                        placa: placa,
                        start_date: start,
                        end_date: end,
                        comprovante: comprovante,
                        mdfe: mdfe,
                    });
                    window.location.href = fluxoUrlComParams(params);
                }
            });
        }
    })();

    function carregarFluxoAsync() {
        const mount = document.getElementById('fluxo-async-mount');
        if (!mount || mount.dataset.loaded === '1') {
            initFluxoInteracoes();
            return;
        }
        const params = fluxoParamsDaPagina();

        function tentarCarregar() {
            const url = fluxoApiUrl(params);
            return fetchComRetry(url, 0, 4)
                .then(function (r) {
                    const pendentesHdr = r.headers.get('X-Pendentes-Coleta');
                    const placasHdr = r.headers.get('X-Fluxo-Placas');
                    const coletaAutoHdr = r.headers.get('X-Coleta-Auto');
                    return r.text().then(function (html) {
                        return {
                            html: html,
                            pendentesHdr: pendentesHdr,
                            placasHdr: placasHdr,
                            coletaAutoHdr: coletaAutoHdr,
                        };
                    });
                })
                .then(function (payload) {
                    mount.innerHTML = payload.html;
                    mount.dataset.loaded = '1';
                    if (payload.pendentesHdr) {
                        const el = document.getElementById('flux-pendentes-coleta');
                        if (el) el.textContent = payload.pendentesHdr;
                    }
                    const autoHdr = payload.coletaAutoHdr;
                    if (autoHdr !== null) {
                        let flagEl = document.getElementById('flux-coleta-auto-flag');
                        if (!flagEl) {
                            flagEl = document.createElement('script');
                            flagEl.id = 'flux-coleta-auto-flag';
                            flagEl.type = 'application/json';
                            document.body.appendChild(flagEl);
                        }
                        flagEl.textContent = autoHdr === '1' ? 'true' : 'false';
                    }
                    if (payload.placasHdr) {
                        try { atualizarDatalistPlacas(JSON.parse(payload.placasHdr)); } catch (e) { /* ignore */ }
                    }
                    initFluxoInteracoes();
                });
        }

        tentarCarregar().catch(function (err) {
            mount.innerHTML = '<div class="fluxo-empty"><p>Não foi possível carregar o fluxo (' + err.message + ').</p>'
                + '<p class="fluxo-loading-hint">Períodos longos podem demorar. Tente um intervalo menor (ex. um mês) e clique em Aplicar.</p>'
                + '<p><button type="button" class="btn-apply" id="fluxo-btn-retry">Tentar novamente</button></p></div>';
            document.getElementById('fluxo-btn-retry')?.addEventListener('click', function () {
                mount.innerHTML = '<div class="fluxo-loading"><p>Carregando fluxo de viagem…</p></div>';
                mount.dataset.loaded = '0';
                carregarFluxoAsync();
            });
        });
    }

    function initFluxoInteracoes() {
    function coletaAutomaticaPendentes() {
        if (!coletaAutomaticaHabilitada()) return;
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

    document.querySelectorAll('.fluxo-link-relatorio').forEach(function (el) {
        el.addEventListener('click', function (e) {
            e.preventDefault();
            const numero = this.dataset.numero;
            if (!numero) return;
            if (typeof window.BIWEB_openRelatorioViagem === 'function') {
                window.BIWEB_openRelatorioViagem(numero);
            } else {
                window.location.href = '/report/viagem/' + encodeURIComponent(numero);
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

    document.querySelectorAll('.fluxo-btn-sati, .fluxo-btn-sati-inline').forEach(function (btn) {
        btn.addEventListener('click', function () {
            iniciarColetaSati(parseNumeros(this.dataset.numeros), this);
        });
    });

    const modalNfe = document.getElementById('flux-modal-nfe-pendente');
    const modalNfeBody = document.getElementById('flux-modal-nfe-pendente-body');
    const btnNfePendente = document.getElementById('btn-nfe-pendentes-cte');
    const btnNfeImprimir = document.getElementById('btn-nfe-pendente-imprimir');
    let nfePendentesDados = null;

    function fecharModalNfe() {
        if (!modalNfe) return;
        modalNfe.hidden = true;
        modalNfe.setAttribute('aria-hidden', 'true');
    }

    function abrirModalNfe() {
        if (!modalNfe) return;
        modalNfe.hidden = false;
        modalNfe.setAttribute('aria-hidden', 'false');
    }

    if (modalNfe) {
        modalNfe.querySelectorAll('[data-flux-modal-nfe-close]').forEach(function (el) {
            el.addEventListener('click', fecharModalNfe);
        });
    }

    function renderNfePendentes(data, filtrosPreservados) {
        if (!modalNfeBody) return;
        nfePendentesDados = data;
        const grupos = data.por_placa || [];
        let html = '<div class="flux-nfe-pendente-filtros no-print">';
        html += '<label>Placa <input type="text" id="nfe-filtro-placa" placeholder="ABC1D23" autocomplete="off"></label>';
        html += '<label>Nº NFe <input type="text" id="nfe-filtro-numero" placeholder="28620" autocomplete="off"></label>';
        html += '<label>Data <input type="date" id="nfe-filtro-data"></label>';
        html += '<button type="button" class="btn-apply btn-apply--secondary btn-apply--sm" id="nfe-filtro-aplicar">Filtrar</button>';
        html += '</div>';
        if (!grupos.length) {
            html += '<p class="flux-modal-empty">' + escapeHtml(data.mensagem || 'Nenhuma NFe pendente de CT-e.') + '</p>';
            modalNfeBody.innerHTML = html;
        } else {
        html += '<div id="nfe-pendente-print-area" class="flux-nfe-pendente-print-area">';
        html += '<p class="flux-nfe-pendente-resumo"><strong>' + escapeHtml(String(data.total || 0)) + '</strong> NFe(s) de transporte sem CT-e emitido.</p>';
        grupos.forEach(function (grupo) {
            html += '<section class="flux-nfe-placa-block">';
            html += '<h3 class="flux-nfe-placa-title"><span class="flux-nfe-placa-badge">' + escapeHtml(grupo.placa) + '</span>';
            html += '<span class="flux-nfe-placa-qtd">' + escapeHtml(String(grupo.qtd)) + ' nota(s)</span></h3>';
            html += '<table class="flux-nfe-pendente-table"><thead><tr>';
            html += '<th>Remetente</th><th>Destino</th><th>Mercadoria</th><th>Emitiu nota</th>';
            html += '<th>Nota</th><th>Data</th><th>Placa</th><th>Valor</th><th>Chave NFe</th>';
            html += '</tr></thead><tbody>';
            (grupo.notas || []).forEach(function (n) {
                html += '<tr>';
                html += '<td>' + escapeHtml(n.remetente || '—') + '</td>';
                html += '<td>' + escapeHtml(n.destino || '—') + '</td>';
                html += '<td>' + escapeHtml(n.mercadoria || '—') + '</td>';
                html += '<td>' + escapeHtml(n.emitiu_nota || '—') + '</td>';
                html += '<td>' + escapeHtml(n.nota_ref || '—') + '</td>';
                html += '<td>' + escapeHtml(n.data_nfe || '—') + '</td>';
                html += '<td>' + escapeHtml(n.placa || grupo.placa || '—') + '</td>';
                html += '<td>' + escapeHtml(n.valor || '—') + '</td>';
                html += '<td class="flux-nfe-chave" title="' + escapeHtml(n.chavenfe || '') + '">…' + escapeHtml(n.chavenfe_curta || '') + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table></section>';
        });
        html += '</div>';
        modalNfeBody.innerHTML = html;
        }

        const btnFiltrar = document.getElementById('nfe-filtro-aplicar');
        if (btnFiltrar) {
            btnFiltrar.addEventListener('click', function () {
                carregarNfePendentes(true);
            });
        }
        if (filtrosPreservados) {
            const placaIn = document.getElementById('nfe-filtro-placa');
            const numIn = document.getElementById('nfe-filtro-numero');
            const dataIn = document.getElementById('nfe-filtro-data');
            if (placaIn && filtrosPreservados.placa != null) placaIn.value = filtrosPreservados.placa;
            if (numIn && filtrosPreservados.numero != null) numIn.value = filtrosPreservados.numero;
            if (dataIn && filtrosPreservados.data != null) dataIn.value = filtrosPreservados.data;
        }
    }

    function carregarNfePendentes(apenasFiltros) {
        if (!modalNfeBody) return;
        const placaEl = document.getElementById('nfe-filtro-placa');
        const numEl = document.getElementById('nfe-filtro-numero');
        const dataEl = document.getElementById('nfe-filtro-data');
        const filtrosAtuais = {
            placa: placaEl ? placaEl.value : '',
            numero: numEl ? numEl.value : '',
            data: dataEl ? dataEl.value : '',
        };
        if (!apenasFiltros) {
            modalNfeBody.innerHTML = '<p class="flux-modal-loading">Consultando notaxml no SATI…</p>';
            abrirModalNfe();
        } else {
            modalNfeBody.querySelector('.flux-nfe-pendente-filtros')?.classList.add('flux-nfe-loading');
        }
        let qs = {};
        const qsEl = document.getElementById('flux-nfe-pendente-qs');
        if (qsEl && qsEl.textContent) {
            try { qs = JSON.parse(qsEl.textContent.trim()); } catch (e) { qs = {}; }
        }
        const params = new URLSearchParams();
        if (qs.start_date) params.set('start_date', qs.start_date);
        if (qs.end_date) params.set('end_date', qs.end_date);
        if (filtrosAtuais.placa.trim()) params.set('placa', filtrosAtuais.placa.trim().toUpperCase());
        if (filtrosAtuais.numero.trim()) params.set('numero_nfe', filtrosAtuais.numero.trim());
        if (filtrosAtuais.data) params.set('data_nfe', filtrosAtuais.data);
        fetch('/api/nfe_pendentes_cte?' + params.toString())
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
            .then(function (res) {
                if (!res.ok || res.data.error) {
                    modalNfeBody.innerHTML = '<p class="flux-modal-empty">' + escapeHtml(res.data.error || 'Erro ao carregar.') + '</p>';
                    return;
                }
                renderNfePendentes(res.data, apenasFiltros ? filtrosAtuais : null);
            })
            .catch(function () {
                modalNfeBody.innerHTML = '<p class="flux-modal-empty">Erro ao consultar NFe pendentes.</p>';
            });
    }

    if (btnNfeImprimir) {
        btnNfeImprimir.addEventListener('click', function () {
            if (!nfePendentesDados || !(nfePendentesDados.por_placa || []).length) {
                alert('Carregue a lista antes de imprimir.');
                return;
            }
            if (modalNfe) {
                modalNfe.hidden = false;
                modalNfe.setAttribute('aria-hidden', 'false');
            }
            document.body.classList.add('flux-print-nfe-pendente');
            window.print();
            window.setTimeout(function () {
                document.body.classList.remove('flux-print-nfe-pendente');
            }, 500);
        });
    }

    if (btnNfePendente) {
        btnNfePendente.addEventListener('click', function () {
            carregarNfePendentes(false);
        });
    }

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
    }

    carregarPlacasFluxo();

    if (document.getElementById('fluxo-async-mount') && document.getElementById('fluxo-async-mount').dataset.loaded !== '1') {
        carregarFluxoAsync();
    } else {
        initFluxoInteracoes();
    }
});
