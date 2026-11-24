"""Login obrigatório por transportadora, perfis de acesso, convites e registro de acessos."""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import timedelta

from flask import jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, logout_user
from sqlalchemy import text

PERFIS = {
    "admin": "Administrador",
    "diretor": "Diretor",
    "comercial": "Comercial",
    "financeiro": "Financeiro",
    "operacao": "Operação",
}

# "*" libera todas as áreas de consulta; a área "admin" é sempre exclusiva do perfil admin.
AREAS_POR_PERFIL = {
    "admin": {"*", "admin"},
    "diretor": {"*"},
    "usuario": {"*"},
    "comercial": {"painel", "comercial"},
    "financeiro": {"painel", "financeiro"},
    "operacao": {"painel", "operacao"},
}

AREA_POR_VISAO = {
    "financeira": "financeiro",
    "custos": "financeiro",
    "frota": "operacao",
    "operacional": "operacao",
    "volume": "comercial",
    "estrategica": "diretoria",
}

AREA_POR_ENDPOINT = {
    "main.visao_comercial": "comercial",
    "main.visao_comercial_analise": "comercial",
    "api.api_gestao_comercial_data": "comercial",
    "main.faturamento_detalhes": "comercial",
    "api.api_faturamento_dashboard_data": "comercial",
    "main.despesas_detalhes": "financeiro",
    "api.api_despesas_dashboard_data": "financeiro",
    "api.api_despesas_audit_data": "financeiro",
    "api.associar_despesa_viagem": "financeiro",
    "api.desvincular_despesa_viagem": "financeiro",
    "main.fluxo_viagem": "operacao",
    "api.api_fluxo_viagem": "operacao",
    "api.api_fluxo_viagem_body": "operacao",
    "api.api_nfe_pendentes_cte": "operacao",
    "api.api_comprovante_descarga_lista": "operacao",
    "api.api_comprovante_descarga_arquivo": "operacao",
    "api.api_fluxo_coletar_comprovantes_automatico": "operacao",
    "main.configuracao": "admin",
    "main.instalacao": "admin",
    "main.instalacao_atualizar": "admin",
    "main.gerenciar_usuarios": "admin",
    "main.adicionar_usuario": "admin",
    "main.get_user_data": "admin",
    "main.editar_usuario": "admin",
    "main.apagar_usuario": "admin",
    "main.gerenciar_grupos_dados": "admin",
    "main.gerenciar_grupos_salvar": "admin",
    "main.iniciar_coleta_endpoint": "admin",
    "main.iniciar_atualizacao_bd_endpoint": "admin",
    "main.iniciar_painel_documentos_endpoint": "admin",
    "main.upload_logo": "admin",
    "api.api_get_robot_logs": "admin",
    "api.api_clear_robot_logs": "admin",
}

ENDPOINTS_PUBLICOS = frozenset({
    "static",
    "auth.login",
    "auth.logout",
    "auth.definir_senha",
    "auth.login_por_slug",
    "auth.login_por_usuario",
})

EMAILS_BLOQUEADOS = frozenset({"admin@local"})
SENHA_MIN = 8
MAX_FALHAS = 5
MAX_FALHAS_IP = 20
JANELA_FALHAS_MIN = 15
CONVITE_HORAS = 72
_SECRET_PADRAO = "uma-chave-secreta-muito-dificil-de-adivinhar"


def auth_obrigatoria() -> bool:
    flag = os.getenv("BIWEB_AUTH_OBRIGATORIA", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo

        return _biweb_multi_tenant_ativo()
    except Exception:
        return False


def obter_secret_key() -> str:
    """SECRET_KEY do ambiente ou, se ausente/padrão, chave aleatória persistida em data/."""
    env = os.getenv("SECRET_KEY", "").strip()
    if env and env != _SECRET_PADRAO:
        return env
    from app.utils.paths import data_root

    path = data_root() / ".flask_secret_key"
    if not path.is_file():
        tmp = path.with_name(f".flask_secret_key.{os.getpid()}.tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(secrets.token_hex(32))
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass
        finally:
            os.unlink(tmp)
    return path.read_text(encoding="utf-8").strip()


def configurar_sessao(app) -> None:
    app.config["SECRET_KEY"] = obter_secret_key()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("BIWEB_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes", "on")
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    horas = int(os.getenv("BIWEB_SESSAO_HORAS", "12") or 12)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=horas)


def tenant_atual() -> str:
    try:
        from infra.tenant_licensing.bi_tenant_context import get_slug

        slug = get_slug()
    except Exception:
        slug = None
    return (slug or session.get("bi_tenant_slug") or "").strip().lower()


def usuario_autenticado() -> bool:
    if not current_user.is_authenticated:
        return False
    atual = hash_fingerprint(getattr(current_user, "password_hash", ""), getattr(current_user, "email", ""))
    if session.get("auth_tenant") != tenant_atual() or session.get("auth_fp") != atual:
        logout_user()
        session.pop("auth_tenant", None)
        return False
    return True


def area_da_request() -> str:
    ep = request.endpoint or ""
    if ep in ("main.visao_bi", "main.visao_bi_analise", "api.api_visao_bi_data"):
        visao = (request.view_args or {}).get("visao_key") or request.args.get("visao", "")
        return AREA_POR_VISAO.get(str(visao).strip().lower(), "painel")
    return AREA_POR_ENDPOINT.get(ep, "painel")


def pode_ver(area: str, perfil: str | None = None) -> bool:
    if not auth_obrigatoria():
        return True
    if perfil is None:
        if not current_user.is_authenticated:
            return False
        perfil = getattr(current_user, "role", "") or ""
    areas = AREAS_POR_PERFIL.get(str(perfil).strip().lower(), set())
    if area == "admin":
        return "admin" in areas
    return "*" in areas or area in areas


def _quer_json() -> bool:
    if (request.path or "").startswith("/api/"):
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = request.accept_mimetypes
    return accept.best == "application/json"


def proteger_request():
    """before_request: exige login no tenant e perfil compatível com a área."""
    if not auth_obrigatoria():
        return None
    ep = request.endpoint or ""
    if ep in ENDPOINTS_PUBLICOS or (request.path or "").startswith("/static/"):
        return None
    if ep.startswith("admin_bi.") or (request.path or "").startswith("/api/admin"):
        return None
    if not usuario_autenticado():
        if _quer_json():
            return jsonify({"error": "login_necessario"}), 401
        destino = request.full_path if request.query_string else request.path
        return redirect(url_for("auth.login", next=destino))
    if not pode_ver(area_da_request()):
        if _quer_json():
            return jsonify({"error": "sem_permissao"}), 403
        return render_template("auth/sem_permissao.html"), 403
    return None


def destino_seguro(nxt: str | None) -> str:
    nxt = (nxt or "").strip()
    if not nxt.startswith("/") or nxt.startswith("//") or "\\" in nxt:
        return url_for("main.index")
    return request.script_root + nxt


def ip_cliente() -> str:
    return (request.remote_addr or "")[:64]


_tabela_log_ok: set[str] = set()


def _garantir_tabela_log(conn) -> None:
    url = os.getenv("DATABASE_URL", "")
    if url in _tabela_log_ok:
        return
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS bi_acessos_log (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP NOT NULL DEFAULT NOW(),
            email TEXT,
            ip TEXT,
            user_agent TEXT,
            evento TEXT NOT NULL,
            ok BOOLEAN NOT NULL
        )
        """
    ))
    _tabela_log_ok.add(url)


def registrar_acesso(email: str, evento: str, ok: bool) -> None:
    from app.data.db_connection import engine

    try:
        with engine.begin() as conn:
            _garantir_tabela_log(conn)
            conn.execute(
                text(
                    "INSERT INTO bi_acessos_log (email, ip, user_agent, evento, ok) "
                    "VALUES (:e, :ip, :ua, :ev, :ok)"
                ),
                {
                    "e": (email or "")[:200],
                    "ip": ip_cliente(),
                    "ua": (request.headers.get("User-Agent") or "")[:300],
                    "ev": evento,
                    "ok": bool(ok),
                },
            )
    except Exception as exc:
        _tabela_log_ok.discard(os.getenv("DATABASE_URL", ""))
        print(f"[auth] falha ao registrar acesso: {exc}")


def login_bloqueado(email: str) -> bool:
    from app.data.db_connection import engine

    try:
        with engine.begin() as conn:
            _garantir_tabela_log(conn)
            falhas = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FILTER (WHERE LOWER(email) = :e), COUNT(*)
                    FROM bi_acessos_log
                    WHERE evento = 'login' AND ok = FALSE
                      AND ts > NOW() - make_interval(mins => :janela)
                      AND ip = :ip
                    """
                ),
                {"janela": JANELA_FALHAS_MIN, "e": email, "ip": ip_cliente()},
            ).first()
        return int(falhas[0] or 0) >= MAX_FALHAS or int(falhas[1] or 0) >= MAX_FALHAS_IP
    except Exception:
        _tabela_log_ok.discard(os.getenv("DATABASE_URL", ""))
        return False


def hash_fingerprint(password_hash: str, email: str = "") -> str:
    base = f"{password_hash or ''}|{(email or '').strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _serializer():
    from itsdangerous import URLSafeTimedSerializer

    return URLSafeTimedSerializer(obter_secret_key(), salt="biweb-convite")


def gerar_token_convite(tenant_slug: str, user_id: int, password_hash: str, email: str) -> str:
    return _serializer().dumps(
        {"t": tenant_slug or "", "u": int(user_id), "h": hash_fingerprint(password_hash, email)}
    )


def ler_token_convite(token: str) -> dict | None:
    try:
        return _serializer().loads(token, max_age=CONVITE_HORAS * 3600)
    except Exception:
        return None


def url_convite(tenant_slug: str, token: str) -> str:
    base = (
        os.getenv("BI_PUBLIC_EXTERNAL_URL", "").strip()
        or os.getenv("NFE_PUBLIC_EXTERNAL_URL", "").strip()
        or "https://dadosfrete.duckdns.org"
    ).rstrip("/")
    if tenant_slug:
        return f"{base}/biweb/{tenant_slug}/definir-senha/{token}"
    return f"{base}/definir-senha/{token}"


def validar_nova_senha(senha: str, confirmacao: str, email: str) -> str | None:
    if len(senha or "") < SENHA_MIN:
        return f"A senha precisa ter pelo menos {SENHA_MIN} caracteres."
    if senha != confirmacao:
        return "As senhas não conferem."
    if senha.strip().lower() == (email or "").strip().lower():
        return "A senha não pode ser igual ao e-mail."
    return None


def criar_ou_atualizar_usuario(tenant_slug: str, email: str, nome: str, perfil: str) -> dict:
    """Cria (ou atualiza nome/perfil) um usuário no banco do tenant e devolve o link de convite."""
    from app.data.db_connection import engine
    from app.data.tenant import ensure_transportadora
    from app.extensions import bcrypt

    email = (email or "").strip().lower()
    nome = (nome or "").strip() or email
    perfil = (perfil or "").strip().lower()
    if "@" not in email:
        raise ValueError("Informe um e-mail válido.")
    if email in EMAILS_BLOQUEADOS:
        raise ValueError("E-mail reservado.")
    if perfil not in PERFIS:
        raise ValueError("Perfil inválido. Use: " + ", ".join(PERFIS))
    if tenant_slug:
        from infra.tenant_licensing.bi_tenant_runtime import prepare_robot_context

        if not prepare_robot_context(tenant_slug):
            raise ValueError(f"Transportadora '{tenant_slug}' não encontrada.")
    tid = ensure_transportadora()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, password_hash FROM usuarios WHERE LOWER(email) = :e AND apartamento_id = :tid"),
            {"e": email, "tid": tid},
        ).first()
        if row:
            conn.execute(
                text("UPDATE usuarios SET nome = :n, role = :r WHERE id = :id"),
                {"n": nome, "r": perfil, "id": row[0]},
            )
            uid, ph = int(row[0]), row[1]
        else:
            ph = bcrypt.generate_password_hash(secrets.token_urlsafe(32)).decode("utf-8")
            uid = conn.execute(
                text(
                    "INSERT INTO usuarios (apartamento_id, nome, email, password_hash, role) "
                    "VALUES (:tid, :n, :e, :h, :r) RETURNING id"
                ),
                {"tid": tid, "n": nome, "e": email, "h": ph, "r": perfil},
            ).scalar()
    token = gerar_token_convite(tenant_slug, uid, ph, email)
    return {
        "id": int(uid),
        "email": email,
        "nome": nome,
        "perfil": perfil,
        "convite_url": url_convite(tenant_slug, token),
        "convite_expira_horas": CONVITE_HORAS,
    }


def listar_usuarios(tenant_slug: str) -> list[dict]:
    from app.data.db_connection import engine
    from app.data.tenant import ensure_transportadora
    from infra.tenant_licensing.bi_tenant_runtime import prepare_robot_context

    if not prepare_robot_context(tenant_slug):
        raise ValueError(f"Transportadora '{tenant_slug}' não encontrada.")
    tid = ensure_transportadora()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, nome, email, role FROM usuarios WHERE apartamento_id = :tid ORDER BY id"),
            {"tid": tid},
        ).mappings().all()
    return [dict(r) for r in rows if (r["email"] or "").lower() not in EMAILS_BLOQUEADOS]
