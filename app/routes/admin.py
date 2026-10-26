"""API admin do BI — provisiona banco/pasta e links por usuário (painel de licenças)."""
from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

admin_bp = Blueprint("admin_bi", __name__, url_prefix="/api/admin")


def _check_admin() -> None:
    esperado = (
        os.getenv("BIWEB_ADMIN_SECRET", "").strip()
        or os.getenv("NFE_ADMIN_SECRET", "").strip()
    )
    enviado = (request.headers.get("X-Admin-Secret") or "").strip()
    if not esperado or enviado != esperado:
        raise PermissionError("Acesso negado.")


@admin_bp.errorhandler(PermissionError)
def _negado(_exc):
    return jsonify({"ok": False, "detail": "Acesso negado."}), 403


@admin_bp.errorhandler(ValueError)
def _valor(exc):
    return jsonify({"ok": False, "detail": str(exc)}), 400


@admin_bp.get("/health")
def health():
    try:
        _check_admin()
    except PermissionError:
        return jsonify({"ok": False, "detail": "Acesso negado."}), 403
    return jsonify({"ok": True, "app": "biweb"})


@admin_bp.get("/tenants")
def listar_tenants():
    try:
        _check_admin()
    except PermissionError:
        return jsonify({"ok": False, "detail": "Acesso negado."}), 403
    from infra.tenant_licensing.acesso_registry import enrich_acesso, list_acessos
    from infra.tenant_licensing.bi_tenant_runtime import TENANTS_ROOT, load_tenant_env

    tenants = []
    if TENANTS_ROOT.is_dir():
        for child in sorted(TENANTS_ROOT.iterdir()):
            if not child.is_dir() or not (child / "tenant.env").is_file():
                continue
            env = load_tenant_env(child.name)
            slug = (env.get("BI_TENANT_SLUG") or child.name).strip().lower()
            tenants.append(
                {
                    "slug": slug,
                    "razao_social": env.get("RAZAO_SOCIAL") or slug,
                    "pg_database": env.get("BI_PG_DATABASE") or "",
                    "ativo": True,
                    "acessos": [
                        enrich_acesso(a) for a in list_acessos(slug)
                    ],
                }
            )
    return jsonify({"ok": True, "tenants": tenants})


@admin_bp.post("/tenants")
def criar_tenant():
    try:
        _check_admin()
    except PermissionError:
        return jsonify({"ok": False, "detail": "Acesso negado."}), 403
    body = request.get_json(silent=True) or {}
    from infra.tenant_licensing.provision import criar_instancia

    try:
        item = criar_instancia(body.get("razao_social") or "", body.get("slug") or None)
    except ValueError as exc:
        return jsonify({"ok": False, "detail": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "detail": str(exc)}), 500
    return jsonify({"ok": True, "tenant": item})


@admin_bp.delete("/tenants/<slug>")
def remover_tenant(slug: str):
    try:
        _check_admin()
    except PermissionError:
        return jsonify({"ok": False, "detail": "Acesso negado."}), 403
    from infra.tenant_licensing.provision import remover_instancia

    try:
        item = remover_instancia(slug, drop_database=True)
    except ValueError as exc:
        return jsonify({"ok": False, "detail": str(exc)}), 404
    except Exception as exc:
        return jsonify({"ok": False, "detail": str(exc)}), 500
    return jsonify({"ok": True, "tenant": item})


@admin_bp.post("/acessos")
def criar_acesso():
    try:
        _check_admin()
    except PermissionError:
        return jsonify({"ok": False, "detail": "Acesso negado."}), 403
    body = request.get_json(silent=True) or {}
    slug = str(body.get("slug") or "").strip()
    if slug.lower() in ("", "auto", "automatico", "automático"):
        slug = ""
    from infra.tenant_licensing.acesso_registry import register_acesso

    try:
        item = register_acesso(
            body.get("nome") or "",
            body.get("tenant_slug") or "",
            slug or None,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "detail": str(exc)}), 400
    return jsonify({"ok": True, "acesso": item})


@admin_bp.patch("/acessos/<slug>")
def alterar_acesso(slug: str):
    try:
        _check_admin()
    except PermissionError:
        return jsonify({"ok": False, "detail": "Acesso negado."}), 403
    body = request.get_json(silent=True) or {}
    from infra.tenant_licensing.acesso_registry import set_acesso_ativo

    try:
        item = set_acesso_ativo(slug, bool(body.get("ativo", True)))
    except ValueError as exc:
        return jsonify({"ok": False, "detail": str(exc)}), 404
    return jsonify({"ok": True, "acesso": item})


@admin_bp.delete("/acessos/<slug>")
def remover_acesso(slug: str):
    try:
        _check_admin()
    except PermissionError:
        return jsonify({"ok": False, "detail": "Acesso negado."}), 403
    from infra.tenant_licensing.acesso_registry import unregister_acesso

    if not unregister_acesso(slug):
        return jsonify({"ok": False, "detail": "Link de usuário BI não encontrado."}), 404
    return jsonify({"ok": True})
