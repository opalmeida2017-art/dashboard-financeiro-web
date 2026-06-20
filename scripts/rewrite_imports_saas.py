"""Reescreve imports após migração para estrutura SaaS."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPLACEMENTS = [
    (r"\bfrom biweb_env import load_env\b", "from app.utils.env_loader import load_env"),
    (r"\bfrom biweb_paths import downloads_dir\b", "from app.utils.paths import downloads_dir"),
    (r"\bfrom biweb_paths import data_root\b", "from app.utils.paths import data_root"),
    (r"\bfrom biweb_paths import app_root\b", "from app.utils.paths import project_root as app_root"),
    (r"\bfrom biweb_paths import\b", "from app.utils.paths import"),
    (r"\bfrom embedded_pg import pg_restore_path\b", "_pg_restore_path"),
    (r"\bfrom extensions import\b", "from app.extensions import"),
    (r"\bfrom config import\b", "from app.config import"),
    (r"\bimport config\b", "from app import config"),
    (r"\bfrom db_connection import\b", "from app.data.db_connection import"),
    (r"\bfrom models import\b", "from app.data.models import"),
    (r"\bfrom tenant import\b", "from app.data.tenant import"),
    (r"\bfrom database import\b", "from app.data.database import"),
    (r"\bimport database as db\b", "from app.data import database as db"),
    (r"\bimport database as db_module\b", "from app.data import database as db_module"),
    (r"\bimport database\b", "from app.data import database"),
    (r"\bimport logic\b", "from app.core import logic"),
    (r"\bfrom logic import\b", "from app.core.logic import"),
    (r"\bimport data_manager as dm\b", "from app.data import data_manager as dm"),
    (r"\bimport data_manager\b", "from app.data import data_manager"),
    (r"\bfrom data_manager import\b", "from app.data.data_manager import"),
    (r"\bimport dre_viagem as dre\b", "from app.core import dre_viagem as dre"),
    (r"\bfrom dre_viagem import\b", "from app.core.dre_viagem import"),
    (r"\bfrom gestao_comercial import\b", "from app.core.gestao_comercial import"),
    (r"\bimport gestao_comercial as gc\b", "from app.core import gestao_comercial as gc"),
    (r"\bfrom visoes_bi import\b", "from app.core.visoes_bi import"),
    (r"\bimport visoes_bi as vb\b", "from app.core import visoes_bi as vb"),
    (r"\bfrom visao_exploratorio import\b", "from app.core.visao_exploratorio import"),
    (r"\bfrom bi_audit import\b", "from app.core.bi_audit import"),
    (r"\bfrom sati_source import\b", "from sati_integration.db.sati_source import"),
    (r"\bfrom sati_queries import\b", "from sati_integration.db.sati_queries import"),
    (r"\bfrom sati_dominios_patch import\b", "from sati_integration.db.sati_dominios_patch import"),
    (r"\bfrom sati_documento import\b", "from sati_integration.db.sati_documento import"),
    (r"\bimport sati_db_restore as sati_restore\b", "from sati_integration.robos import sati_db_restore as sati_restore"),
    (r"\bimport sati_db_restore as sr\b", "from sati_integration.robos import sati_db_restore as sr"),
    (r"\bimport sati_db_restore as s\b", "from sati_integration.robos import sati_db_restore as s"),
    (r"\bimport sati_db_restore\b", "from sati_integration.robos import sati_db_restore"),
    (r"\bfrom sati_db_restore import\b", "from sati_integration.robos.sati_db_restore import"),
    (r"\bfrom bi_tenant_runtime import\b", "from infra.tenant_licensing.bi_tenant_runtime import"),
    (r"\bfrom bi_tenant_context import\b", "from infra.tenant_licensing.bi_tenant_context import"),
    (r"\bfrom licenca_remota import\b", "from infra.tenant_licensing.licenca_remota import"),
    (r"\bfrom fluxo_monitor import\b", "from infra.cloud.fluxo_monitor import"),
    (r"\bfrom limpar_dados import\b", "from scripts.limpar_dados import"),
    (r"\bfrom \.helpers import\b", "from app.utils.helpers import"),
    (r"\bfrom blueprints\.helpers import\b", "from app.utils.helpers import"),
    (r"\bfrom blueprints\.main import\b", "from app.routes.web import"),
    (r"\bfrom blueprints\.auth import\b", "from app.routes.auth import"),
    (r"\bfrom blueprints\.api import\b", "from app.routes.api import"),
    (r"\bimport app as main_app\b", "from app import app as main_app"),
    (r"\bfrom app import app as application\b", "from app import app as application"),
]

TEMPLATE_MAP = {
    "'index.html'": "'dashboards/index.html'",
    '"index.html"': '"dashboards/index.html"',
    "'visao_comercial_index.html'": "'dashboards/visao_comercial_index.html'",
    "'visao_comercial_analise.html'": "'dashboards/visao_comercial_analise.html'",
    "'visao_bi_index.html'": "'dashboards/visao_bi_index.html'",
    "'visao_bi_analise.html'": "'dashboards/visao_bi_analise.html'",
    "'fluxo_viagem.html'": "'dashboards/fluxo_viagem.html'",
    "'configuracao.html'": "'admin/configuracao.html'",
    "'gerenciar_usuarios.html'": "'admin/gerenciar_usuarios.html'",
    "'instalacao.html'": "'admin/instalacao.html'",
    '"acesso_negado.html"': '"auth/acesso_negado.html"',
    "'acesso_negado.html'": "'auth/acesso_negado.html'",
}

PG_RESTORE_HELPER = '''
def _pg_restore_path():
    import os
    import shutil
    custom = os.getenv("SATI_PG_RESTORE", "").strip()
    if custom and os.path.isfile(custom):
        return custom
    found = shutil.which("pg_restore")
    if found:
        return found
    raise RuntimeError("pg_restore não encontrado. Defina SATI_PG_RESTORE no .env")
'''


def rewrite_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text

    for pat, repl in REPLACEMENTS:
        text = re.sub(pat, repl, text)

    if "_pg_restore_path" in text and "def _pg_restore_path" not in text:
        text = PG_RESTORE_HELPER.strip() + "\n\n" + text
        text = text.replace("_pg_restore_path", "_pg_restore_path")
        text = re.sub(
            r"(\s+)_pg_restore_path",
            r"\1pg_restore_path = _pg_restore_path",
            text,
        )
        text = text.replace("pg_restore_path()", "_pg_restore_path()")

    if path.name == "web.py":
        for old, new in TEMPLATE_MAP.items():
            text = text.replace(old, new)
        # Remove biweb_env desktop instalacao helpers
        text = text.replace(
            "    from biweb_env import save_robo_credentials, setup_completed\n",
            "",
        )
        text = text.replace("save_robo_credentials(url_sat, usuario, senha)\n\n", "")
        text = text.replace(
            "    if request.method == 'GET' and setup_completed():\n        return redirect(url_for('main.index'))\n\n",
            "",
        )

    if path.name == "auth.py":
        for old, new in TEMPLATE_MAP.items():
            text = text.replace(old, new)

    if path == ROOT / "app" / "__init__.py":
        pass  # already correct

    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    changed = 0
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if "venv" in path.parts or ".venv" in path.parts:
            continue
        if rewrite_file(path):
            print("updated", path.relative_to(ROOT))
            changed += 1
    print(f"done: {changed} files")


if __name__ == "__main__":
    main()
