from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session, Response, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import current_user
from extensions import login_required
from werkzeug.utils import secure_filename
import os
import getpass
import redis
from rq import Queue
import logic
import data_manager as dm
import database as db
import uuid
from limpar_dados import limpar_dados_importados
from datetime import datetime, timedelta
from .helpers import get_target_apartment_id, is_admin_in_context, parse_filters, normalize_placa_filter
from extensions import bcrypt
from db_connection import engine
import time
from weasyprint import HTML, CSS
import secrets 
from PIL import Image
from rembg import remove

# --- CORREÇÃO: REMOVIDO ---
# As linhas UPLOAD_FOLDER e ALLOWED_EXTENSIONS foram removidas.
# Elas são configuradas no app.py (dentro de create_app)
# e lidas via current_app.config
# ---------------------------

main_bp = Blueprint('main', __name__)

# --- CORREÇÃO: REMOVIDO ---
# A criação da pasta (os.makedirs) também foi movida para o app.py
# ---------------------------

# --- CORREÇÃO: Função atualizada para ler do app.config ---
# Esta função é chamada DE DENTRO de uma rota, onde o current_app é seguro.
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
# --- FIM DAS CORREÇÕES ---


@main_bp.context_processor
def inject_cache_buster():
    return dict(cache_buster=int(time.time()))

REDIS_URL = os.environ.get('REDIS_URL')
redis_conn = redis.Redis.from_url(REDIS_URL) if REDIS_URL else None

@main_bp.route('/')
@login_required
def index():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        flash("Não foi possível identificar a transportadora desta instalação.", "error")
        return redirect(url_for('main.index'))

    logo_filename = logic.get_apartment_logo(apartamento_id_alvo)
    logo_url = None
    if logo_filename:
        # O logo_filename já deve conter o caminho relativo (ex: '1/logo.png')
        logo_url = url_for('static', filename=f'uploads/{logo_filename}')

    filters = parse_filters(request.args)
    resolver = getattr(logic, "resolve_date_filters", dm.resolver_intervalo_consulta)
    start_eff, end_eff = resolver(
        apartamento_id_alvo, filters['start_date_obj'], filters['end_date_obj']
    )
    if not filters['start_date_str']:
        filters['start_date_str'] = start_eff.strftime('%Y-%m-%d')
        filters['end_date_str'] = end_eff.strftime('%Y-%m-%d')
        filters['start_date_obj'] = start_eff
        filters['end_date_obj'] = end_eff
    summary_data = logic.get_dashboard_summary(
        apartamento_id=apartamento_id_alvo,
        start_date=start_eff,
        end_date=end_eff,
        placa_filter=filters['placa'],
        filial_filter=filters['filial'],
        tipo_negocio_filter=filters['tipo_negocio']
    )
    
    placas = logic.get_unique_plates_with_types(apartamento_id=apartamento_id_alvo)
    filiais = logic.get_unique_filiais(apartamento_id=apartamento_id_alvo)
    tipos_negocio = logic.get_unique_negocios(apartamento_id=apartamento_id_alvo)
    placa_filtrada = filters['placa'] and filters['placa'] != 'Todos'
    
    return render_template('index.html', # Mude aqui para o nome correto do seu template principal
                           summary=summary_data,
                           placas=placas,
                           filiais=filiais,
                           tipos_negocio=tipos_negocio,
                           selected_placa=filters['placa'],
                           selected_filial=filters['filial'],
                           selected_start_date=filters['start_date_str'],
                           selected_end_date=filters['end_date_str'],
                           selected_tipo_negocio=filters['tipo_negocio'],
                           placa_filtrada=placa_filtrada,
                           logo_url=logo_url)
    
@main_bp.route('/faturamento_detalhes')
@login_required
def faturamento_detalhes():
    qs = request.query_string.decode('utf-8')
    url = url_for('main.visao_bi', visao_key='volume')
    return redirect(f'{url}?{qs}' if qs else url)


@main_bp.route('/despesas_detalhes')
@login_required
def despesas_detalhes():
    qs = request.query_string.decode('utf-8')
    url = url_for('main.visao_bi', visao_key='custos')
    return redirect(f'{url}?{qs}' if qs else url)


@main_bp.route('/visao_comercial')
@login_required
def visao_comercial():
    import gestao_comercial as gc
    filters = parse_filters(request.args)
    return render_template(
        'visao_comercial_index.html',
        analises=gc.ANALISES_LIST,
        selected_start_date=filters['start_date_str'],
        selected_end_date=filters['end_date_str'],
        selected_placa=filters['placa'],
        selected_filial=filters['filial'],
    )


@main_bp.route('/visao_comercial/<int:analise_id>')
@login_required
def visao_comercial_analise(analise_id: int):
    import gestao_comercial as gc
    if analise_id not in gc.ANALISES:
        flash('Análise comercial não encontrada.', 'error')
        return redirect(url_for('main.visao_comercial'))
    filters = parse_filters(request.args)
    analise = dict(gc.ANALISES[analise_id])
    analise['id'] = analise_id
    return render_template(
        'visao_comercial_analise.html',
        analise=analise,
        analise_id=analise_id,
        selected_start_date=filters['start_date_str'],
        selected_end_date=filters['end_date_str'],
        selected_placa=filters['placa'],
        selected_filial=filters['filial'],
    )


@main_bp.route('/visao/<visao_key>')
@login_required
def visao_bi(visao_key: str):
    import visoes_bi as vb
    if visao_key not in vb.VISOES:
        flash('Visão não encontrada.', 'error')
        return redirect(url_for('main.index'))
    visao = vb.VISOES[visao_key]
    filters = parse_filters(request.args)
    return render_template(
        'visao_bi_index.html',
        visao_key=visao_key,
        visao_titulo=visao['titulo'],
        visao_subtitulo=visao['subtitulo'],
        analises=vb.list_analises(visao_key),
        selected_start_date=filters['start_date_str'],
        selected_end_date=filters['end_date_str'],
        selected_placa=filters['placa'],
        selected_filial=filters['filial'],
    )


@main_bp.route('/visao/<visao_key>/<int:analise_id>')
@login_required
def visao_bi_analise(visao_key: str, analise_id: int):
    import visoes_bi as vb
    meta = vb.get_visao_meta(visao_key, analise_id)
    if not meta:
        flash('Análise não encontrada.', 'error')
        return redirect(url_for('main.visao_bi', visao_key=visao_key))
    visao = vb.VISOES[visao_key]
    filters = parse_filters(request.args)
    return render_template(
        'visao_bi_analise.html',
        visao_key=visao_key,
        visao_titulo=visao['titulo'],
        analise=meta,
        analise_id=analise_id,
        badge=visao['badge'],
        badge_class=visao['badge_class'],
        selected_start_date=filters['start_date_str'],
        selected_end_date=filters['end_date_str'],
        selected_placa=filters['placa'],
        selected_filial=filters['filial'],
    )


def _resolver_intervalo_fluxo_viagem(apartamento_id, start_date, end_date):
    """Fluxo operacional: padrão 30 dias (evita ano inteiro no SATI)."""
    if start_date and end_date:
        return dm.resolver_intervalo_consulta(apartamento_id, start_date, end_date)
    fim = datetime.now().replace(hour=23, minute=59, second=59)
    inicio = (fim - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio, fim


@main_bp.route('/fluxo_viagem')
@login_required
def fluxo_viagem():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        flash("Não foi possível identificar a empresa.", "error")
        return redirect(url_for('auth.logout'))

    filters = parse_filters(request.args)
    start_eff, end_eff = _resolver_intervalo_fluxo_viagem(
        apartamento_id_alvo, filters['start_date_obj'], filters['end_date_obj']
    )
    if not filters['start_date_str']:
        filters['start_date_str'] = start_eff.strftime('%Y-%m-%d')
        filters['end_date_str'] = end_eff.strftime('%Y-%m-%d')

    historico_placa = request.args.get('historico') == '1'
    placa_arg = normalize_placa_filter(request.args.get('placa') or filters.get('placa'))
    qs_base = request.query_string.decode('utf-8')

    if historico_placa and placa_arg and placa_arg != 'Todos':
        rows = logic.get_fluxo_viagem_historico(
            apartamento_id=apartamento_id_alvo,
            start_date=start_eff,
            end_date=end_eff,
            placa=placa_arg,
            filial_filter=filters['filial'],
        )
        modo = 'historico'
        placa_historico = placa_arg
    else:
        rows = logic.get_fluxo_veiculos_resumo(
            apartamento_id=apartamento_id_alvo,
            start_date=start_eff,
            end_date=end_eff,
            filial_filter=filters['filial'],
        )
        modo = 'lista'
        placa_historico = None

    comprovante_filtro = dm.normalizar_filtro_comprovante_fluxo(
        request.args.get('comprovante')
    )
    total_antes_filtro = len(rows)
    rows = dm.filtrar_fluxo_por_comprovante(rows, comprovante_filtro)

    if modo == 'lista' and rows:
        placas = [
            {"placa": r.get("placa"), "tipo": ""}
            for r in sorted(rows, key=lambda x: x.get("placa") or "")
            if r.get("placa") and not r.get("sem_viagem_periodo")
        ]
        visto = set()
        placas_unicas = []
        for p in placas:
            pl = p["placa"]
            if pl not in visto:
                visto.add(pl)
                placas_unicas.append(p)
        placas = placas_unicas
    else:
        # Histórico: placas do resumo (cache SATI) — evita relFilViagensCliente + despesas.
        resumo_placas = logic.get_fluxo_veiculos_resumo(
            apartamento_id=apartamento_id_alvo,
            start_date=start_eff,
            end_date=end_eff,
            filial_filter=filters['filial'],
        )
        placas = [
            {"placa": r.get("placa"), "tipo": ""}
            for r in sorted(resumo_placas, key=lambda x: x.get("placa") or "")
            if r.get("placa")
        ]

    import json

    pendentes_coleta = dm.coletar_numeros_pendentes_comprovante(rows)

    try:
        from fluxo_monitor import salvar_lista_fluxo

        salvar_lista_fluxo(
            apartamento_id_alvo,
            rows,
            start_date=filters['start_date_str'],
            end_date=filters['end_date_str'],
            modo=modo,
            numeros_pendentes=pendentes_coleta,
        )
    except Exception as e:
        print(f"Aviso: não foi possível salvar lista do fluxo: {e}")

    return render_template(
        'fluxo_viagem.html',
        rows=rows,
        placas=placas,
        modo=modo,
        placa_historico=placa_historico,
        qs_base=qs_base,
        selected_placa=placa_arg,
        selected_start_date=filters['start_date_str'],
        selected_end_date=filters['end_date_str'],
        selected_comprovante_filtro=comprovante_filtro,
        comprovante_filtro_opcoes=dm.FLUXO_FILTRO_COMPROVANTE_OPCOES,
        total_antes_filtro_comprovante=total_antes_filtro,
        pendentes_coleta_json=json.dumps(pendentes_coleta),
    )


@main_bp.route('/gerenciar-grupos-dados')
@login_required
def gerenciar_grupos_dados():
    apartamento_id_alvo = get_target_apartment_id()
    logic.sync_expense_groups(apartamento_id_alvo) 
    df_flags = logic.get_group_flags_with_tipo_d_status(apartamento_id_alvo)
    flags_dict = df_flags.set_index('group_name').to_dict('index') if not df_flags.empty else {}
    return jsonify(flags_dict)

@main_bp.route('/gerenciar-grupos-salvar', methods=['POST'])
@login_required
def gerenciar_grupos_salvar():
    apartamento_id_alvo = get_target_apartment_id()
    if not is_admin_in_context():
        flash("Acesso negado.", "error")
        return redirect(url_for('main.index'))
        
    all_groups = logic.get_all_expense_groups(apartamento_id_alvo)
    update_data = {}
    
    for group in all_groups:
        classification = request.form.get(f"{group}_class", 'nenhum')
        incluir_tipo_d = f"{group}_tipo_d" in request.form
        update_data[group] = {'classification': classification, 'incluir_tipo_d': incluir_tipo_d}
        
    logic.update_all_group_flags(apartamento_id_alvo, update_data)
    flash('Classificação de grupos salva com sucesso!', 'success')
    return redirect(url_for('main.index'))

def _iniciar_atualizacao_banco_sati(apartamento_id_alvo: int, *, allow_setup: bool = False):
    """Valida e dispara atualização do banco SATI (SQL). Retorna (ok, payload_json, http_code)."""
    logs_url = url_for('main.configuracao', auto_logs=1)

    if not allow_setup and not is_admin_in_context():
        return False, {
            'status': 'erro',
            'mensagem': 'Apenas administradores podem atualizar o banco SATI.',
        }, 403

    if not os.getenv('SATI_DATABASE_URL', '').strip():
        return False, {
            'status': 'erro',
            'mensagem': 'SATI_DATABASE_URL não configurada no servidor (.env).',
        }, 400

    configs_robo = logic.ler_configuracoes_robo(apartamento_id_alvo)
    if not dm.robo_credenciais_configuradas(configs_robo):
        return False, {
            'status': 'erro',
            'mensagem': (
                'Preencha e salve URL, usuário e senha na aba Conexão SAT desta tela '
                '(Configurações do Robô).'
            ),
            'redirect': logs_url,
        }, 400

    execution_mode = os.getenv('EXECUTION_MODE', 'async')
    if execution_mode == 'sync':
        ok = logic.executar_atualizacao_bd_sati(apartamento_id_alvo)
        dm.clear_data_cache(apartamento_id_alvo)
        if ok:
            flash('Banco SATI atualizado com sucesso!', 'success')
            return True, {
                'status': 'sucesso',
                'mensagem': 'Banco SATI atualizado! Os dados do painel vêm do PostgreSQL.',
                'redirect': logs_url,
            }, 200
        return False, {
            'status': 'erro',
            'mensagem': 'Falha na atualização. Veja os logs abaixo.',
            'redirect': logs_url,
        }, 200

    if not redis_conn:
        return False, {
            'status': 'erro',
            'mensagem': 'Serviço de fila (Redis) não está disponível. Use EXECUTION_MODE=sync no .env.',
        }, 500

    q = Queue(connection=redis_conn)
    q.enqueue(logic.executar_atualizacao_bd_sati, apartamento_id_alvo, job_timeout=7200)
    flash('Atualização do banco SATI iniciada.', 'success')
    return True, {
        'status': 'sucesso',
        'mensagem': 'Atualização iniciada. Acompanhe o progresso nos logs.',
        'redirect': logs_url,
    }, 200


@main_bp.route('/iniciar-coleta', methods=['POST'])
@login_required
def iniciar_coleta_endpoint():
    """Atualiza o banco SATI via SAT (não exporta mais planilhas)."""
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({'status': 'erro', 'mensagem': 'Transportadora não identificada.'}), 400
    try:
        ok, payload, code = _iniciar_atualizacao_banco_sati(apartamento_id_alvo)
        return jsonify(payload), code
    except Exception as e:
        flash(f'Erro ao iniciar atualização: {e}', 'error')
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 500


@main_bp.route('/iniciar-atualizacao-bd', methods=['POST'])
@login_required
def iniciar_atualizacao_bd_endpoint():
    """Alias do endpoint de atualização do banco (compatibilidade)."""
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({'status': 'erro', 'mensagem': 'Transportadora não identificada.'}), 400
    try:
        ok, payload, code = _iniciar_atualizacao_banco_sati(apartamento_id_alvo)
        return jsonify(payload), code
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 500


def _parse_numeros_internos_painel() -> list[int]:
    """Lê números internos do CT-e (JSON, form ou query)."""
    import re

    bruto = []
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        val = payload.get("numeros_internos") or payload.get("numeros")
        if isinstance(val, list):
            bruto = val
        elif isinstance(val, str):
            bruto = re.split(r"[,;\s]+", val.strip())
    else:
        val = (
            request.form.get("numeros_internos")
            or request.args.get("numeros_internos")
            or request.args.get("numeros")
        )
        if val:
            bruto = re.split(r"[,;\s]+", str(val).strip())

    numeros = []
    for item in bruto:
        s = str(item).strip()
        if not s:
            continue
        try:
            numeros.append(int(s))
        except (TypeError, ValueError):
            continue
    return numeros


def _iniciar_painel_documentos_sati(apartamento_id_alvo: int):
    """Dispara robô Painel de Documentos (comprovantes descarga)."""
    logs_url = url_for('main.configuracao', auto_logs=1)

    if not is_admin_in_context():
        return False, {
            'status': 'erro',
            'mensagem': 'Apenas administradores podem executar o robô do Painel de Documentos.',
        }, 403

    configs_robo = logic.ler_configuracoes_robo(apartamento_id_alvo)
    if not dm.robo_credenciais_configuradas(configs_robo):
        return False, {
            'status': 'erro',
            'mensagem': (
                'Preencha e salve URL, usuário e senha na aba Conexão SAT '
                '(Configurações do Robô).'
            ),
            'redirect': logs_url,
        }, 400

    baixar_pdfs = request.args.get('baixar_pdfs', 'true').lower() not in ('0', 'false', 'no')
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if payload.get('baixar_pdfs') is False:
            baixar_pdfs = False
        elif payload.get('baixar_pdfs') is True:
            baixar_pdfs = True
    data_ini = (request.args.get('data_ini') or '').strip() or None
    data_fim = (request.args.get('data_fim') or '').strip() or None
    numeros_internos = _parse_numeros_internos_painel()
    if not numeros_internos:
        return False, {
            'status': 'erro',
            'mensagem': (
                'Informe pelo menos um número interno do CT-e '
                '(conhecimento.numero), ex.: 7801.'
            ),
            'redirect': logs_url,
        }, 400

    execution_mode = os.getenv('EXECUTION_MODE', 'async')
    if execution_mode == 'sync':
        ok = logic.executar_painel_documentos_sati(
            apartamento_id_alvo,
            data_ini=data_ini,
            data_fim=data_fim,
            numeros_internos=numeros_internos,
            baixar_pdfs=baixar_pdfs,
        )
        dm.clear_data_cache(apartamento_id_alvo)
        if ok:
            flash('Painel de Documentos coletado com sucesso!', 'success')
            return True, {
                'status': 'sucesso',
                'mensagem': 'Comprovantes listados no cache. O fluxo de viagem usará esses dados.',
                'redirect': logs_url,
            }, 200
        return False, {
            'status': 'erro',
            'mensagem': 'Falha na coleta do painel. Veja os logs abaixo.',
            'redirect': logs_url,
        }, 200

    if not redis_conn:
        return False, {
            'status': 'erro',
            'mensagem': 'Serviço de fila (Redis) não está disponível. Use EXECUTION_MODE=sync no .env.',
        }, 500

    q = Queue(connection=redis_conn)
    q.enqueue(
        logic.executar_painel_documentos_sati,
        apartamento_id_alvo,
        data_ini=data_ini,
        data_fim=data_fim,
        numeros_internos=numeros_internos,
        baixar_pdfs=baixar_pdfs,
        job_timeout=3600,
    )
    flash('Coleta do Painel de Documentos iniciada.', 'success')
    return True, {
        'status': 'sucesso',
        'mensagem': 'Robô iniciado. Acompanhe o progresso nos logs.',
        'redirect': logs_url,
    }, 200


@main_bp.route('/iniciar-painel-documentos', methods=['POST'])
@login_required
def iniciar_painel_documentos_endpoint():
    """Painéis → Painel de Documentos (lista comprovantes de descarga no SATI)."""
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({'status': 'erro', 'mensagem': 'Transportadora não identificada.'}), 400
    try:
        ok, payload, code = _iniciar_painel_documentos_sati(apartamento_id_alvo)
        return jsonify(payload), code
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 500


@main_bp.route('/instalacao', methods=['GET', 'POST'])
def instalacao():
    """Assistente inicial do BIWEB Desktop (link, usuário, senha SAT)."""
    from biweb_env import save_robo_credentials, setup_completed
    from tenant import ensure_transportadora

    apartamento_id_alvo = ensure_transportadora()

    if request.method == 'GET' and setup_completed():
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        nome = request.form.get('nome_transportadora', '').strip() or 'Minha Transportadora'
        url_sat = request.form.get('URL_LOGIN', '').strip()
        usuario = request.form.get('USUARIO_ROBO', '').strip()
        senha = request.form.get('SENHA_ROBO', '').strip()
        email_admin = request.form.get('email_admin', '').strip()
        senha_admin = request.form.get('senha_admin', '').strip()

        if not all([url_sat, usuario, senha]):
            flash('Preencha URL, usuário e senha do SAT.', 'error')
            return redirect(url_for('main.instalacao'))

        logic.update_apartment_details(apartamento_id_alvo, nome, 'ativo', '', '')
        logic.salvar_configuracoes_robo(
            apartamento_id_alvo,
            {
                'URL_LOGIN': url_sat,
                'USUARIO_ROBO': usuario,
                'SENHA_ROBO': senha,
                'USE_SATI_SOURCE': 'true',
            },
        )
        save_robo_credentials(url_sat, usuario, senha)

        if email_admin and senha_admin:
            from sqlalchemy import text
            from db_connection import engine

            with engine.connect() as conn:
                existe = conn.execute(
                    text('SELECT id FROM usuarios WHERE email = :e'),
                    {'e': email_admin},
                ).first()
            if not existe:
                ph = bcrypt.generate_password_hash(senha_admin).decode('utf-8')
                logic.add_user_to_apartment(
                    apartamento_id_alvo, 'Administrador', email_admin, ph, 'admin'
                )

        if request.form.get('atualizar_agora'):
            flash('Atualização do banco SATI iniciada. Aguarde nos logs…', 'info')
            ok, payload, _code = _iniciar_atualizacao_banco_sati(
                apartamento_id_alvo, allow_setup=True
            )
            if ok and payload.get('redirect'):
                return redirect(payload['redirect'])
            if not ok:
                flash(payload.get('mensagem', 'Falha ao iniciar atualização.'), 'error')
                return redirect(url_for('main.configuracao', auto_logs=1))

        flash('Instalação concluída! O painel está pronto.', 'success')
        return redirect(url_for('main.index'))

    configs = logic.ler_configuracoes_robo(apartamento_id_alvo) or {}
    transportadora = logic.get_apartment_details(apartamento_id_alvo) or {}
    return render_template(
        'instalacao.html',
        configs=configs,
        transportadora=transportadora,
        transportadora_nome=transportadora.get('nome_empresa', ''),
    )


@main_bp.route('/instalacao/atualizar', methods=['POST'])
def instalacao_atualizar():
    apartamento_id_alvo = get_target_apartment_id()
    ok, payload, code = _iniciar_atualizacao_banco_sati(apartamento_id_alvo)
    return jsonify(payload), code


@main_bp.route('/configuracao', methods=['GET', 'POST'])
@login_required
def configuracao():
    if not is_admin_in_context():
        flash("Acesso negado. Você precisa ser um administrador para ver esta página.", "error")
        return redirect(url_for('main.index'))
    
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        flash("Sessão inválida.", "error")
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        nome_transportadora = request.form.get('nome_transportadora', '').strip()
        if nome_transportadora:
            logic.update_apartment_details(
                apartamento_id_alvo, nome_transportadora, 'ativo', '', ''
            )
        configs_to_save = {
            'URL_LOGIN': request.form.get('URL_LOGIN'),
            'USUARIO_ROBO': request.form.get('USUARIO_ROBO'),
            'SENHA_ROBO': request.form.get('SENHA_ROBO'),
            'USE_SATI_SOURCE': 'true',
            'live_monitoring_enabled': 'live_monitoring_enabled' in request.form,
        }
        logic.salvar_configuracoes_robo(apartamento_id_alvo, configs_to_save)
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('main.configuracao'))
    
    configs_salvas = logic.ler_configuracoes_robo(apartamento_id_alvo)
    transportadora = logic.get_apartment_details(apartamento_id_alvo) or {}
    auto_logs = request.args.get('auto_logs') in ('1', 'true', 'yes')
    return render_template(
        'configuracao.html',
        configs=configs_salvas,
        transportadora=transportadora,
        auto_logs=auto_logs,
    )

@main_bp.route('/gerenciar_usuarios')
@login_required
def gerenciar_usuarios():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index')) 

    users = logic.get_users_for_apartment(apartamento_id_alvo)
    
    current_apartment_logo = logic.get_apartment_logo(apartamento_id_alvo)

    return render_template('gerenciar_usuarios.html', users=users, current_apartment_logo=current_apartment_logo)

@main_bp.route('/gerenciar-usuarios/adicionar', methods=['POST'])
@login_required
def adicionar_usuario():
    if not is_admin_in_context():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    nome = request.form.get('nome')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'usuario')

    if not all([nome, email, password]):
        flash('Todos os campos são obrigatórios.', 'error')
        return redirect(url_for('main.gerenciar_usuarios'))

    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    success, message = logic.add_user_to_apartment(
        apartamento_id=apartamento_id_alvo, nome=nome, email=email,
        password_hash=password_hash, role=role
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('main.gerenciar_usuarios'))

@main_bp.route('/gerenciar-usuarios/dados/<int:user_id>', methods=['GET'])
@login_required
def get_user_data(user_id):
    if not is_admin_in_context():
        return jsonify({'error': 'Acesso negado'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    user = logic.get_user_by_id(user_id, apartamento_id_alvo)
    if user:
        return jsonify(user)
    return jsonify({'error': 'Utilizador não encontrado'}), 404

@main_bp.route('/gerenciar-usuarios/editar/<int:user_id>', methods=['POST'])
@login_required
def editar_usuario(user_id):
    if not is_admin_in_context():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    nome = request.form.get('nome')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'usuario')

    if not all([nome, email]):
        flash('Nome e email são obrigatórios.', 'error')
        return redirect(url_for('main.gerenciar_usuarios'))

    new_password_hash = bcrypt.generate_password_hash(password).decode('utf-8') if password else None
    success, message = logic.update_user_in_apartment(
        user_id=user_id, apartamento_id=apartamento_id_alvo, nome=nome,
        email=email, role=role, new_password_hash=new_password_hash
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('main.gerenciar_usuarios'))

@main_bp.route('/gerenciar-usuarios/apagar/<int:user_id>', methods=['POST'])
@login_required
def apagar_usuario(user_id):
    if not is_admin_in_context():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    apartamento_id_alvo = get_target_apartment_id()
    if user_id == current_user.id:
        flash('Não pode apagar a sua própria conta de administrador.', 'error')
        return redirect(url_for('main.gerenciar_usuarios'))

    success, message = logic.delete_user_from_apartment(user_id, apartamento_id_alvo)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('main.gerenciar_usuarios'))

@main_bp.cli.command("criar-admin")
def criar_admin_command():
    print("--- Assistente: primeira transportadora e administrador ---")
    nome_empresa = input("Nome da transportadora: ")
    admin_nome = input("Seu nome completo: ")
    admin_email = input("Seu email (será seu login): ")
    admin_password = getpass.getpass("Digite uma senha para você: ")

    if not all([nome_empresa, admin_nome, admin_email, admin_password]):
        print("Erro: Todos os campos são obrigatórios.")
        return

    password_hash = bcrypt.generate_password_hash(admin_password).decode('utf-8')
    success, message = logic.create_apartment_and_admin(nome_empresa, admin_nome, admin_email, password_hash)
    
    if success:
        print(f"\nSUCESSO: {message}")
    else:
        print(f"\nERRO: {message}")
        


# Adicione esta função para formatar datas no template
@main_bp.app_template_filter('format_date')
def format_date_filter(s):
    if not s:
        return ''
    try:
        # Assumindo que a data vem como 'YYYY-MM-DDTHH:MM:SS'
        dt = datetime.fromisoformat(s.split('T')[0])
        return dt.strftime('%d/%m/%Y')
    except:
        return s

@main_bp.route('/render_report/viagem', methods=['POST'])
@login_required
def render_viagem_report():
    report_data = request.json.get('data')
    # Usamos o novo template para renderizar o relatório
    return render_template('reports/report_viagem.html', data=report_data)

@main_bp.route('/report/print/<int:numero>')
@login_required
def print_viagem_report(numero):
    apartamento_id_alvo =  get_target_apartment_id()
    if not apartamento_id_alvo:
        flash("Apartamento não selecionado.", "danger")
        return redirect(url_for('main.index'))

    dias_janela = request.args.get('dias_janela', type=int, default=0)
    data = logic.get_relatorio_viagem_data(apartamento_id_alvo, numero, dias_janela)

    if not data:
        flash("Dados do relatório de viagem não encontrados.", "danger")
        return redirect(url_for('main.index'))

    logo_filename = logic.get_apartment_logo(apartamento_id_alvo)
    
    print(f"DEBUG: print_viagem_report - Logo filename obtido: {logo_filename}")
    
    logo_url = None
    if logo_filename:
        # Corrigido: usa o caminho relativo correto para o logo
        logo_url = url_for('static', filename=f'uploads/{logo_filename}', _external=True)

    
    print(f"DEBUG: print_viagem_report - Logo URL gerada: {logo_url}")
    print(f"DEBUG: print_viagem_report - Apartamento ID: {apartamento_id_alvo}")


    html_string = render_template('reports/report_viagem.html', 
                                  data=data, 
                                  logo_url=logo_url, 
                                  apartamento_id=apartamento_id_alvo)
    
    # Caminho para o seu CSS de impressão
    css_path = os.path.join(current_app.root_path, 'static', 'print.css')
    
    # Criar um objeto HTML a partir da string e base_url
    # A base_url é crucial para o WeasyPrint encontrar recursos como imagens e CSS
    html_doc = HTML(string=html_string, base_url=request.base_url)

    # Carregar o CSS
    css = CSS(filename=css_path)

    # Gerar o PDF
    pdf_file = html_doc.write_pdf(stylesheets=[css])

    response = Response(pdf_file, mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'inline; filename=relatorio_viagem_{numero}.pdf'
    return response
    
@main_bp.route('/upload_logo', methods=['POST'])
@login_required
def upload_logo():
 

    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        flash("Transportadora não identificada para upload de logo.", "danger")
        return redirect(url_for('main.index'))

    if 'file' not in request.files:
        flash("Nenhum arquivo de logo enviado.", "danger")
        return redirect(url_for('main.gerenciar_usuarios'))

    file = request.files['file']
    if file.filename == '':
        flash("Nenhum arquivo de logo selecionado.", "danger")
        return redirect(url_for('main.gerenciar_usuarios'))

    if file and allowed_file(file.filename):
        
        # LÓGICA PARA APAGAR O LOGO ANTIGO
        old_logo_filename = logic.get_apartment_logo(apartamento_id_alvo)
        if old_logo_filename:
            old_logo_path = os.path.join(current_app.static_folder, 'uploads', old_logo_filename)
            if os.path.exists(old_logo_path):
                try:
                    os.remove(old_logo_path)
                    print(f"DEBUG: Logo antigo removido com sucesso: {old_logo_path}")
                except OSError as e:
                    print(f"AVISO: Não foi possível remover o logo antigo {old_logo_path}: {e}")

        # LÓGICA PARA PROCESSAR E SALVAR O NOVO LOGO
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
        logo_filename_base = f"logo_apto_{apartamento_id_alvo}_{uuid.uuid4().hex}"
        logo_filename_temp = f"{logo_filename_base}.{ext}"
        
        # O 'upload_folder' deve vir do app.config
        upload_folder_base = current_app.config['UPLOAD_FOLDER']
        upload_folder_apto = os.path.join(upload_folder_base, str(apartamento_id_alvo))
        
        os.makedirs(upload_folder_apto, exist_ok=True)
        temp_filepath = os.path.join(upload_folder_apto, logo_filename_temp)
        
        file.save(temp_filepath)

        try:
            input_image = Image.open(temp_filepath)
            output_image = remove(input_image)
            
            final_logo_filename = f"{logo_filename_base}.png"
            final_filepath = os.path.join(upload_folder_apto, final_logo_filename)
            output_image.save(final_filepath, format="PNG")
            
            os.remove(temp_filepath)
            
            logo_path_to_db = os.path.join(str(apartamento_id_alvo), final_logo_filename).replace('\\', '/')
            logic.update_apartment_logo(apartamento_id_alvo, logo_path_to_db)
            
            flash("Logo atualizado com sucesso!", "success")
        except Exception as e:
            flash(f"Erro ao processar o logo: {e}", "danger")
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            return redirect(url_for('main.gerenciar_usuarios'))
    else:
        flash('Tipo de arquivo não permitido.', 'error')

    return redirect(url_for('main.gerenciar_usuarios'))