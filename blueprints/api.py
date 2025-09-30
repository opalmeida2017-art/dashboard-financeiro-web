# blueprints/api.py
from flask import Blueprint, jsonify, request, Response,current_app
from flask_login import login_required
from sqlalchemy import text
import json
import time
from datetime import datetime, timedelta
import logic

from extensions import bcrypt
from db_connection import engine
from .helpers import get_target_apartment_id, is_admin_in_context, super_admin_required, parse_filters
api_bp = Blueprint('api', __name__, url_prefix='/api')

def _parse_filters():
    filters = {
        'placa': request.args.get('placa', 'Todos'),
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
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400

    filters = _parse_filters()
    monthly_data = logic.get_monthly_summary(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial'],
        tipo_negocio_filter=filters['tipo_negocio']
    )
    return jsonify(monthly_data.to_dict(orient='records'))

@api_bp.route('/get_robot_logs')
@login_required
def api_get_robot_logs():
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400
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
        return jsonify({"status": "error", "message": "Contexto do apartamento não encontrado"}), 400
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
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400
    filters = _parse_filters()
    dashboard_data = logic.get_faturamento_details_dashboard_data(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(dashboard_data)

@api_bp.route('/despesas_dashboard_data')
@login_required
def api_despesas_dashboard_data():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400
    filters = _parse_filters()
    dashboard_data = logic.get_despesas_details_dashboard_data(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(dashboard_data)

@api_bp.route('/despesas_audit_data')
@login_required
def api_despesas_audit_data():
    apartamento_id_alvo = get_target_apartment_id()
    if apartamento_id_alvo is None:
        return jsonify({"error": "Contexto do apartamento não encontrado"}), 400
    filters = _parse_filters()
    audit_data = logic.get_expense_audit_data(
        apartamento_id=apartamento_id_alvo,
        start_date=filters['start_date_obj'],
        end_date=filters['end_date_obj'],
        placa_filter=filters['placa'],
        filial_filter=filters['filial']
    )
    return jsonify(audit_data)

@api_bp.route('/relatorio_viagem/<int:num_conhec>')
@login_required
def api_relatorio_viagem(num_conhec):
    apartamento_id_alvo = get_target_apartment_id()
    if not apartamento_id_alvo:
        return jsonify({"error": "Apartamento não encontrado."}), 400
    
    # --- INÍCIO DA CORREÇÃO ---
    try:
        dados_relatorio = logic.get_relatorio_viagem_data(apartamento_id_alvo, num_conhec)
        
        # Se a lógica interna já identificou um erro (ex: Viagem não encontrada), retorne-o.
        if "error" in dados_relatorio:
            return jsonify(dados_relatorio), 404

        # Formata os valores de moeda e percentual para exibição
        for key in ['frete_bruto', 'adiantamentos', 'taxas', 'descontos', 'total_receitas', 'total_custos', 'lucro_prejuizo']:
            if dados_relatorio.get(key) is not None:
                dados_relatorio[key] = current_app.jinja_env.filters['currency'](dados_relatorio[key])
        if dados_relatorio.get('margem') is not None:
            dados_relatorio['margem'] = current_app.jinja_env.filters['percentage'](dados_relatorio['margem'])
        
        custos_formatados = {k: current_app.jinja_env.filters['currency'](v) for k, v in dados_relatorio.get("custos_detalhados", {}).items()}
        dados_relatorio["custos_detalhados"] = custos_formatados

        return jsonify(dados_relatorio)

    except Exception as e:
        # Se qualquer erro inesperado acontecer (KeyError, TypeError, etc.),
        # ele será capturado aqui.
        print(f"ERRO CRÍTICO na API /api/relatorio_viagem para o CT-e {num_conhec}: {e}")
        # Retorna uma resposta JSON de erro, em vez de deixar o servidor quebrar.
        return jsonify({"error": "Ocorreu um erro inesperado no servidor ao processar os dados desta viagem."}), 500
    # --- FIM DA CORREÇÃO ---
    
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
@super_admin_required
def status_stream():
    def event_generator():
        while True:
            try:
                with engine.connect() as conn:
                    two_minutes_ago = datetime.now() - timedelta(minutes=2)
                    query = text("SELECT apartamento_id FROM tb_user_activity WHERE last_seen_timestamp >= :time_limit")
                    result = conn.execute(query, {"time_limit": two_minutes_ago})
                    active_ids = [row[0] for row in result]
                
                data_json = json.dumps({"active_apartments": active_ids})
                yield f"data: {data_json}\n\n"
                
                time.sleep(5)
            except Exception as e:
                error_data = json.dumps({"error": str(e)})
                yield f"data: {error_data}\n\n"
                time.sleep(5)

    return Response(event_generator(), mimetype='text/event-stream')