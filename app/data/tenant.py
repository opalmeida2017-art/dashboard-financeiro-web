"""
Instalação única por transportadora (sem multi-apartamento).
Coluna legada no banco: apartamento_id / tabela apartamentos.
"""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import text

from app.data import database as db


def default_transportadora_id() -> int:
    """ID configurado que exista em apartamentos; senão o primeiro registro."""
    for key in ("BIWEB_TRANSPORTADORA_ID", "BIWEB_AUTO_APT"):
        raw = os.getenv(key, "").strip()
        if not raw:
            continue
        try:
            tid = int(raw)
        except ValueError:
            continue
        try:
            with db.engine.connect() as conn:
                if conn.execute(
                    text("SELECT id FROM apartamentos WHERE id = :id"),
                    {"id": tid},
                ).first():
                    return tid
        except Exception:
            pass
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM apartamentos ORDER BY id LIMIT 1")
            ).first()
        if row:
            return int(row[0])
    except Exception:
        pass
    return 1


def get_transportadora_id() -> int:
    """ID da transportadora desta instalação (uma por servidor/.exe)."""
    try:
        from infra.tenant_licensing.bi_tenant_runtime import _biweb_multi_tenant_ativo

        if _biweb_multi_tenant_ativo():
            return default_transportadora_id()
    except Exception:
        pass
    try:
        from flask import has_request_context
        from flask_login import current_user

        if has_request_context() and current_user.is_authenticated:
            aid = getattr(current_user, "apartamento_id", None) or getattr(
                current_user, "transportadora_id", None
            )
            if aid is not None:
                tid = int(aid)
                try:
                    with db.engine.connect() as conn:
                        if conn.execute(
                            text("SELECT id FROM apartamentos WHERE id = :id"),
                            {"id": tid},
                        ).first():
                            return tid
                except Exception:
                    pass
    except Exception:
        pass
    return default_transportadora_id()


def get_transportadora_nome(transportadora_id: int | None = None) -> str:
    tid = transportadora_id or get_transportadora_id()
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT nome_empresa FROM apartamentos WHERE id = :id"),
                {"id": tid},
            ).first()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass
    return os.getenv("BIWEB_TRANSPORTADORA_NOME", "Transportadora")


_NOMES_EXIBICAO_IGNORAR = frozenset({
    "teste",
    "minha transportadora",
    "transportadora",
})


def nome_exibicao_navbar(valor: str | None) -> str:
    """Oculta nomes de teste/placeholder no cabeçalho do painel."""
    nome = (valor or "").strip()
    if not nome or nome.lower() in _NOMES_EXIBICAO_IGNORAR:
        return ""
    return nome


def get_transportadora_nome_exibicao(transportadora_id: int | None = None) -> str:
    return nome_exibicao_navbar(get_transportadora_nome(transportadora_id))


def ensure_transportadora() -> int:
    """Garante uma única transportadora no banco (primeira instalação)."""
    nome = os.getenv("BIWEB_TRANSPORTADORA_NOME", "Minha Transportadora").strip()
    default_id = default_transportadora_id()
    hoje = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db.engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, nome_empresa FROM apartamentos ORDER BY id LIMIT 1")
        ).first()

        if row:
            tid = int(row[0])
            if not (row[1] or "").strip() and nome:
                conn.execute(
                    text("UPDATE apartamentos SET nome_empresa = :n WHERE id = :id"),
                    {"n": nome, "id": tid},
                )
            return tid

        ins = conn.execute(
            text(
                """
                INSERT INTO apartamentos (nome_empresa, status, data_criacao, slug)
                VALUES (:nome, 'ativo', :data, 'principal')
                RETURNING id
                """
            ),
            {"nome": nome, "data": hoje},
        )
        new_id = ins.scalar()
        return int(new_id) if new_id is not None else default_id


def ensure_local_admin(transportadora_id: int | None = None) -> None:
    """Garante um administrador local se a instalação ainda não tiver usuários."""
    tid = transportadora_id or default_transportadora_id()
    try:
        with db.engine.connect() as conn:
            if conn.execute(
                text("SELECT id FROM usuarios WHERE apartamento_id = :tid LIMIT 1"),
                {"tid": tid},
            ).first():
                return
    except Exception:
        return

    from app.extensions import bcrypt

    email = os.getenv("BIWEB_DEV_ADMIN_EMAIL", "admin@local").strip() or "admin@local"
    nome = os.getenv("BIWEB_DEV_ADMIN_NOME", "Administrador").strip() or "Administrador"
    senha = os.getenv("BIWEB_DEV_ADMIN_PASSWORD", "admin")
    ph = bcrypt.generate_password_hash(senha).decode("utf-8")
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO usuarios (apartamento_id, nome, email, password_hash, role)
                    VALUES (:tid, :nome, :email, :hash, 'admin')
                    """
                ),
                {"tid": tid, "nome": nome, "email": email, "hash": ph},
            )
    except Exception:
        pass


def try_auto_login() -> bool:
    """Sessão automática do admin da transportadora desta instalação."""
    try:
        from flask_login import current_user, login_user
        from app.extensions import load_user

        if current_user.is_authenticated:
            return True
    except Exception:
        return False

    tid = default_transportadora_id()
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id FROM usuarios WHERE apartamento_id = :tid
                    ORDER BY CASE WHEN role = 'admin' THEN 0 ELSE 1 END, id
                    LIMIT 1
                    """
                ),
                {"tid": tid},
            ).first()
    except Exception:
        return False
    if not row:
        return False
    from app.extensions import load_user
    from flask_login import login_user

    user = load_user(row[0])
    if user:
        login_user(user, remember=True)
        return True
    return False


ensure_dev_admin = ensure_local_admin
