"""Reorganiza BIWEB para arquitetura 100% Web/SaaS."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DELETE = [
    "teste.iss",
    "BIWEBDesktop.spec",
    "build_desktop.ps1",
    "biweb_launcher.py",
    "biweb_bootstrap.py",
    "biweb_paths.py",
    "biweb_env.py",
    "embedded_pg.py",
    "requirements-desktop.txt",
    "calcular_valor.py",
    "coletor_principal.py",
    "app.py",
    "installer/biweb.iss",
    "docs/INSTALADOR_DESKTOP.md",
    "docs/MODO_LEVE_SEM_PG_EMBUTIDO.md",
]

MOVES = {
    "config.py": "app/config.py",
    "extensions.py": "app/extensions.py",
    "blueprints/api.py": "app/routes/api.py",
    "blueprints/auth.py": "app/routes/auth.py",
    "blueprints/main.py": "app/routes/web.py",
    "blueprints/helpers.py": "app/utils/helpers.py",
    "logic.py": "app/core/logic.py",
    "dre_viagem.py": "app/core/dre_viagem.py",
    "bi_audit.py": "app/core/bi_audit.py",
    "gestao_comercial.py": "app/core/gestao_comercial.py",
    "visoes_bi.py": "app/core/visoes_bi.py",
    "visao_exploratorio.py": "app/core/visao_exploratorio.py",
    "db_connection.py": "app/data/db_connection.py",
    "database.py": "app/data/database.py",
    "models.py": "app/data/models.py",
    "tenant.py": "app/data/tenant.py",
    "data_manager.py": "app/data/data_manager.py",
    "agendamento_email.py": "app/utils/agendamento_email.py",
    "relatorio_execucao.py": "app/utils/exports/relatorio_execucao.py",
    "relatorio_itens.py": "app/utils/exports/relatorio_itens.py",
    "relatorio_suporte.py": "app/utils/exports/relatorio_suporte.py",
    "sati_source.py": "sati_integration/db/sati_source.py",
    "sati_queries.py": "sati_integration/db/sati_queries.py",
    "sati_dominios_patch.py": "sati_integration/db/sati_dominios_patch.py",
    "sati_documento.py": "sati_integration/db/sati_documento.py",
    "robos/base_robo.py": "sati_integration/robos/base_robo.py",
    "robos/coletor_atualizacao_bd.py": "sati_integration/robos/coletor_atualizacao_bd.py",
    "robos/coletor_painel_documentos.py": "sati_integration/robos/coletor_painel_documentos.py",
    "comprovante_descarga.py": "sati_integration/robos/comprovante_descarga.py",
    "sati_db_restore.py": "sati_integration/robos/sati_db_restore.py",
    "Dockerfile": "infra/cloud/Dockerfile",
    "docker-compose.yml": "infra/cloud/docker-compose.yml",
    "render.yaml": "infra/cloud/render.yaml",
    "Procfile": "infra/cloud/Procfile",
    "startup.sh": "infra/cloud/startup.sh",
    "runtime.txt": "infra/cloud/runtime.txt",
    "worker.py": "infra/cloud/worker.py",
    "fluxo_monitor.py": "infra/cloud/fluxo_monitor.py",
    "licenca_remota.py": "infra/tenant_licensing/licenca_remota.py",
    "bi_tenant_context.py": "infra/tenant_licensing/bi_tenant_context.py",
    "bi_tenant_runtime.py": "infra/tenant_licensing/bi_tenant_runtime.py",
    "alembic.ini": "migrations/alembic.ini",
    "limpar_dados.py": "scripts/limpar_dados.py",
    "analisar_dump.py": "scripts/analisar_dump.py",
    "diagnostico_chave.py": "scripts/diagnostico_chave.py",
    "sync_groups.py": "scripts/sync_groups.py",
}

TEMPLATE_MOVES = {
    "templates/index.html": "frontend/templates/dashboards/index.html",
    "templates/index_dashboard_content.html": "frontend/templates/dashboards/index_dashboard_content.html",
    "templates/visao_comercial_index.html": "frontend/templates/dashboards/visao_comercial_index.html",
    "templates/visao_comercial_analise.html": "frontend/templates/dashboards/visao_comercial_analise.html",
    "templates/visao_bi_index.html": "frontend/templates/dashboards/visao_bi_index.html",
    "templates/visao_bi_analise.html": "frontend/templates/dashboards/visao_bi_analise.html",
    "templates/fluxo_viagem.html": "frontend/templates/dashboards/fluxo_viagem.html",
    "templates/faturamento_detalhes.html": "frontend/templates/dashboards/faturamento_detalhes.html",
    "templates/despesas_detalhes.html": "frontend/templates/dashboards/despesas_detalhes.html",
    "templates/acesso_negado.html": "frontend/templates/auth/acesso_negado.html",
    "templates/login.html": "frontend/templates/auth/login.html",
    "templates/configuracao.html": "frontend/templates/admin/configuracao.html",
    "templates/gerenciar_usuarios.html": "frontend/templates/admin/gerenciar_usuarios.html",
    "templates/instalacao.html": "frontend/templates/admin/instalacao.html",
    "templates/layout.html": "frontend/templates/layout.html",
    "templates/reports/print_report.html": "frontend/templates/reports/print_report.html",
    "templates/reports/report_viagem.html": "frontend/templates/reports/report_viagem.html",
}

DIRS = [
    "app/routes",
    "app/core",
    "app/data",
    "app/utils/exports",
    "sati_integration/db",
    "sati_integration/robos",
    "frontend/static",
    "frontend/templates/dashboards",
    "frontend/templates/auth",
    "frontend/templates/admin",
    "frontend/templates/reports",
    "infra/cloud",
    "infra/tenant_licensing",
    "migrations/sql_scripts",
]


def ensure_dirs():
    for d in DIRS:
        p = ROOT / d
        p.mkdir(parents=True, exist_ok=True)
        init = p / "__init__.py"
        if not init.exists() and d.split("/")[0] in ("app", "sati_integration"):
            init.write_text("", encoding="utf-8")
    for pkg in ("app", "sati_integration", "infra"):
        (ROOT / pkg / "__init__.py").write_text("", encoding="utf-8")


def safe_move(src_rel: str, dst_rel: str):
    src = ROOT / src_rel
    dst = ROOT / dst_rel
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    shutil.move(str(src), str(dst))
    print(f"  moved {src_rel} -> {dst_rel}")


def move_tree(src_rel: str, dst_rel: str):
    src = ROOT / src_rel
    dst = ROOT / dst_rel
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(src), str(dst))
    print(f"  moved tree {src_rel} -> {dst_rel}")


def main():
    ensure_dirs()

    for rel in DELETE:
        p = ROOT / rel
        if p.exists():
            p.unlink()
            print(f"  deleted {rel}")

    for src, dst in MOVES.items():
        safe_move(src, dst)

    for src, dst in TEMPLATE_MOVES.items():
        safe_move(src, dst)

    move_tree("static", "frontend/static")
    move_tree("alembic", "migrations/alembic")

    sql_src = ROOT / "sql"
    if sql_src.exists():
        for f in sql_src.iterdir():
            if f.is_file():
                safe_move(f"sql/{f.name}", f"migrations/sql_scripts/{f.name}")
        if not any(sql_src.iterdir()):
            sql_src.rmdir()

    criar = ROOT / "criar_dominios_public.sql"
    if criar.exists():
        safe_move("criar_dominios_public.sql", "migrations/sql_scripts/criar_dominios_public.sql")

    for empty in ("blueprints", "robos", "templates"):
        d = ROOT / empty
        if d.exists() and not any(d.rglob("*")):
            shutil.rmtree(d)

    print("done structure")


if __name__ == "__main__":
    main()
