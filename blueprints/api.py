# blueprints/api.py
from flask import Blueprint, jsonify, request, Response,current_app
from extensions import login_required
from sqlalchemy import text
import json
import re
import time
from datetime import datetime, timedelta
import logic
import data_manager as dm

from extensions import bcrypt
from db_connection import engine
from .helpers import get_target_apartment_id, is_admin_in_context, parse_filters, normalize_placa_filter
from tenant import get_transportadora_id
api_bp = Blueprint('api', __name__, url_prefix='/api')

def _parse_filters():
    placas = request.args.getlist('placa')
    filters = {
        'placa': placas[0] if len(placas) == 1 else (placas if placas else 'Todos'),
        'filial': request.args.getlist('filial'),
        'start_date_str': request.args.get('start_date', ''),
        'end_date_str': request.args.get('end_date', ''),
        'tipo_negocio': request.args.get('tipo_negocio', 'Todos')
    }
    try:
        filters['start_date_obj'] = datetime.strptime(filters['start_date_str'], '%Y-%m-%d') if filters['start_date_str'] else None
        filters['end_date_obj'] = datetime.strptime(filters['end_date_str'], '%Y-%m-%d').replace(hour=23, minute=59, second=59) if filters['end_date_str'] else None
    except ValueError:
        filters['start_date_obj'] = None
        filters['end_date_obj'] = None
    return filters

@api_bp.route('/monthly_summary')
@login_required
def api_monthly_summary():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Transportadora não identificada"}), 400

    filters = _parse_filters()
    resolver = getattr(logic, "resolve_date_filters", dm.resolver_intervalo_consulta)
    start_eff, end_eff = resolver(
        apartamento_id_alvo, filters['start_date_obj'], filters['end_date_obj']
    )
    monthly_data = logic.get_monthly_summary(
        apartamento_id=apartamento_id_alvo,
        start_date=start_eff,
        end_date=end_eff,
        placa_filter=filters['placa'],
        filial_filter=filters['filial'],
        tipo_negocio_filter=filters['tipo_negocio']
    )
    records = monthly_data.to_dict(orient='records')
    for row in records:
        for key in ('Faturamento', 'Custo', 'DespesasGerais', 'DespesaTipoD', 'TotalDespesas'):
            if key in row and row[key] is not None:
                try:
                    row[key] = float(row[key])
                except (TypeError, ValueError):
                    row[key] = 0.0
    return jsonify(records)

@api_bp.route('/get_robot_logs')
@login_required
def api_get_robot_logs():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"error": "Transportadora não identificada"}), 400
    try:
        with engine.connect() as conn:
            query = text("SELECT timestamp, mensagem FROM tb_logs_robo WHERE apartamento_id = :apt_id ORDER BY timestamp DESC LIMIT 100")
            result = conn.execute(query, {"apt_id": apartamento_id_alvo})
            logs = [{"timestamp": row[0].strftime('%d/%m/%Y %H:%M:%S') if row[0] else '', "mensagem": row[1]} for row in result]
            return jsonify(logs)
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar logs: {e}"}), 500

@api_bp.route('/clear_robot_logs', methods=['POST'])
@login_required
def api_clear_robot_logs():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"status": "error", "message": "Transportadora não identificada"}), 400
    try:
        with engine.connect() as conn:
            query = text("DELETE FROM tb_logs_robo WHERE apartamento_id = :apt_id")
            conn.execute(query, {"apt_id": apartamento_id_alvo})
            conn.commit()
        return jsonify({"status": "success", "message": "Logs limpos com sucesso!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro ao limpar logs: {e}"}), 500

@api_bp.route('/faturamento_dashboard_data')
@login_required
def api_faturamento_dashboard_data():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Transportadora não identificada"}), 400
    
    # A função _parse_filters() já busca o 'tipo_negocio', então está correta.
    filters = _parse_filters()
    
    dashboard_data = logic.get_faturamento_details_dashboard_data(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial'],
        # --- LINHA ADICIONADA ---
        tipo_negocio_filter=filters['tipo_negocio']
    )
    return jsonify(dashboard_data)

@api_bp.route('/despesas_dashboard_data')
@login_required
def api_despesas_dashboard_data():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Transportadora não identificada"}), 400
    filters = _parse_filters()
    resolver = getattr(logic, "resolve_date_filters", dm.resolver_intervalo_consulta)
    start_eff, end_eff = resolver(
        apartamento_id_alvo, filters["start_date_obj"], filters["end_date_obj"]
    )
    dashboard_data = logic.get_despesas_details_dashboard_data(
        apartamento_id=apartamento_id_alvo,
        start_date=start_eff,
        end_date=end_eff,
        placa_filter=filters['placa'],
        filial_filter=filters['filial'],
        tipo_negocio_filter=filters['tipo_negocio']
    )
    return jsonify(dashboard_data)

@api_bp.route('/fluxo_viagem')
@login_required
def api_fluxo_viagem():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Transportadora não identificada"}), 400
    filters = _parse_filters()
    resolver = getattr(logic, "resolve_date_filters", dm.resolver_intervalo_consulta)
    start_eff, end_eff = resolver(
        apartamento_id_alvo, filters["start_date_obj"], filters["end_date_obj"]
    )
    historico = request.args.get("historico") == "1"
    placa = normalize_placa_filter(request.args.get("placa") or filters.get("placa"))
    if historico and placa and placa != "Todos":
        rows = logic.get_fluxo_viagem_historico(
            apartamento_id_alvo, start_eff, end_eff, placa, filters["filial"]
        )
    else:
        rows = logic.get_fluxo_veiculos_resumo(
            apartamento_id_alvo, start_eff, end_eff, filters["filial"]
        )
    comprovante_filtro = dm.normalizar_filtro_comprovante_fluxo(
        request.args.get("comprovante")
    )
    rows = dm.filtrar_fluxo_por_comprovante(rows, comprovante_filtro)
    return jsonify(rows)

@api_bp.route('/despesas_audit_data')
@login_required
def api_despesas_audit_data():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Transportadora não identificada"}), 400
    filters = _parse_filters()
    audit_data = logic.get_expense_audit_data(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial'],
        # --- LINHA ADICIONADA ---
        tipo_negocio_filter=filters['tipo_negocio']
    )
    return jsonify(audit_data)

@api_bp.route('/relatorio_viagem/<int:numero>') # ALTERADO AQUI
@login_required
def api_relatorio_viagem(numero): # ALTERADO AQUI
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"error": "Apartamento não encontrado."}), 400
    
    try:
        dias_janela = request.args.get('dias_janela', 10, type=int)
        dados_relatorio = logic.get_relatorio_viagem_data(apartamento_id_alvo, numero, dias_janela=dias_janela) # ALTERADO AQUI
        
        if "error" in dados_relatorio:
            return jsonify(dados_relatorio), 404

        return jsonify(dados_relatorio)

    except Exception as e:
        print(f"ERRO CRÍTICO na API /api/relatorio_viagem para o CT-e {numero}: {e}") # ALTERADO AQUI
        return jsonify({"error": "Ocorreu um erro inesperado no servidor ao processar os dados desta viagem."}), 500


@api_bp.route('/comprovante_descarga')
@login_required
def api_comprovante_descarga_lista():
    """Texto e metadados dos comprovantes (Painel de Documentos / cache)."""
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"error": "Transportadora não identificada."}), 400

    bruto = request.args.get("numeros") or request.args.get("numero") or ""
    numeros = []
    for parte in re.split(r"[,;\s]+", str(bruto).strip()):
        if not parte:
            continue
        try:
            numeros.append(int(parte))
        except (TypeError, ValueError):
            continue
    if not numeros:
        return jsonify({"error": "Informe numeros (número interno do CT-e)."}), 400

    payload = logic.get_comprovante_descarga_payload(apartamento_id_alvo, numeros)
    if not payload.get("itens"):
        return jsonify({
            "itens": [],
            "mensagem": "Nenhum comprovante no cache. Use «Buscar no SATI» no fluxo de viagem.",
        }), 404
    return jsonify(payload)


@api_bp.route('/fluxo/coletar_comprovantes_automatico', methods=['POST'])
@login_required
def api_fluxo_coletar_comprovantes_automatico():
    """
    Dispara o robô Painel de Documentos para CT-es em fase comprovante de descarga.
    Body JSON opcional: { "numeros_internos": [7801, ...] }
    Se omitido, usa números enviados ou lista vazia (cliente envia da tela).
    """
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"status": "erro", "mensagem": "Transportadora não identificada."}), 400

    numeros = []
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        val = payload.get("numeros_internos") or payload.get("numeros")
        if isinstance(val, list):
            for item in val:
                try:
                    numeros.append(int(item))
                except (TypeError, ValueError):
                    pass

    baixar = True
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if payload.get("baixar_pdfs") is False:
            baixar = False

    resultado = logic.disparar_coleta_comprovantes_fluxo(
        apartamento_id_alvo,
        numeros,
        baixar_pdfs=baixar,
    )
    code = 200 if resultado.get("status") in ("sucesso", "ignorado") else 400
    return jsonify(resultado), code


@api_bp.route('/comprovante_descarga/<int:numero>/arquivo')
@login_required
def api_comprovante_descarga_arquivo(numero: int):
    from flask import send_file
    import os

    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"error": "Transportadora não identificada."}), 400

    path = logic.resolver_arquivo_comprovante_descarga(apartamento_id_alvo, numero)
    if not path or not os.path.isfile(path):
        return jsonify({"error": "Arquivo não encontrado. Execute a coleta com download no SATI."}), 404

    return send_file(path, mimetype="application/pdf", as_attachment=False)


@api_bp.route('/heartbeat', methods=['POST'])
@login_required
def api_heartbeat():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"status": "error"}), 400
    
    try:
        with engine.connect() as conn:
            query = text("""
                INSERT INTO tb_user_activity (apartamento_id, last_seen_timestamp)
                VALUES (:apt_id, NOW())
                ON CONFLICT (apartamento_id) DO UPDATE
                SET last_seen_timestamp = NOW();
            """)
            conn.execute(query, {"apt_id": apartamento_id_alvo})
            conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error"}), 500

@api_bp.route('/status_stream')
@login_required
def status_stream():
    def event_generator():
        while True:
            try:
                tid = get_transportadora_id()
                active_ids = [tid]
                data_json = json.dumps({"active_transportadoras": active_ids})
                yield f"data: {data_json}\n\n"
                
                time.sleep(5)
            except Exception as e:
                error_data = json.dumps({"error": str(e)})
                yield f"data: {error_data}\n\n"
                time.sleep(5)

    return Response(event_generator(), mimetype='text/event-stream')

# Em blueprints/api.py, substitua estas duas funções:

@api_bp.route('/associar_despesa_viagem', methods=['POST'])
@login_required
def associar_despesa_viagem():
    data = request.get_json()
    apartamento_id_alvo = get_target_apartment_id()
    numero = data.get('numero') # ALTERADO AQUI
    cod_item_nota = data.get('cod_item_nota')

    if not all([apartamento_id_alvo, numero, cod_item_nota]):
        return jsonify({"status": "error", "message": "Dados incompletos."}), 400

    try:
        with engine.connect() as conn:
            with conn.begin():
                query_delete = text('DELETE FROM despesas_viagem_excluidas WHERE apartamento_id = :apt_id AND numero = :numero AND "coditemnota" = :cod_item_nota')
                conn.execute(query_delete, {"apt_id": apartamento_id_alvo, "numero": numero, "cod_item_nota": cod_item_nota})

                query_insert = text("""
                    INSERT INTO despesas_viagem_associadas (apartamento_id, numero, "coditemnota")
                    VALUES (:apt_id, :numero, :cod_item_nota)
                    ON CONFLICT (apartamento_id, numero, "coditemnota") DO NOTHING;
                """)
                conn.execute(query_insert, {"apt_id": apartamento_id_alvo, "numero": numero, "cod_item_nota": cod_item_nota})
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_bp.route('/desvincular_despesa_viagem', methods=['POST'])
@login_required
def desvincular_despesa_viagem():
    data = request.get_json()
    apartamento_id_alvo = get_target_apartment_id()
    numero = data.get('numero') # ALTERADO AQUI
    cod_item_nota = data.get('cod_item_nota')

    if not all([apartamento_id_alvo, numero, cod_item_nota]):
        return jsonify({"status": "error", "message": "Dados incompletos para desvincular."}), 400

    try:
        with engine.connect() as conn:
            with conn.begin():
                query = text("""
                    DELETE FROM despesas_viagem_associadas 
                    WHERE apartamento_id = :apt_id AND "coditemnota" = :cod_item_nota AND numero = :numero
                """)
                conn.execute(query, {
                    "apt_id": apartamento_id_alvo, 
                    "cod_item_nota": cod_item_nota,
                    "numero": numero
                })
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"ERRO CRÍTICO ao desvincular despesa: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500