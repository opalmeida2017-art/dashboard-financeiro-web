#!/usr/bin/env python3
"""
Prepara ambiente de desenvolvimento Windows: bancos, schema app, restore SATI.

Uso (após sync do Debian):
    python scripts/sync_from_debian.py --tenant transporte-brasil
    python scripts/setup_dev_windows.py --tenant transporte-brasil
    python run_dev.py

Opções:
    --tenant transporte-brasil|jeremias|rio-bonito|wcarlos
    --skip-restore     só cria bancos + tabelas app (sem pg_restore)
    --force-restore    restaura SATI mesmo se schema já tiver dados
    --sync-first       roda sync_from_debian antes do setup
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

TENANTS = {
    "transporte-brasil": {
        "label": "Transporte Brasil",
        "schema": "c3332",
        "apartamento_id": 3,
        "slug": "transporte-brasil",
    },
    "jeremias": {
        "label": "Jeremias",
        "schema": "c3332",
        "apartamento_id": 6,
        "slug": "jeremias",
    },
    "rio-bonito": {
        "label": "Rio Bonito",
        "schema": "c3219",
        "apartamento_id": 2,
        "slug": "rio-bonito",
    },
    "wcarlos": {
        "label": "W Carlos",
        "schema": "c2910",
        "apartamento_id": 1,
        "slug": "wcarlos",
    },
}

PG_BIN_CANDIDATES = [
    Path(r"C:\Program Files\PostgreSQL\17\bin"),
    Path(r"C:\Program Files\PostgreSQL\16\bin"),
]


def _parse_pg_url(url: str) -> dict:
    u = urlparse(url)
    return {
        "host": u.hostname or "localhost",
        "port": str(u.port or 5432),
        "user": unquote(u.username or "postgres"),
        "password": unquote(u.password or ""),
        "database": (u.path or "/").lstrip("/") or "postgres",
    }


def _find_pg_bin() -> Path:
    env = os.getenv("SATI_PG_RESTORE", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p.parent
    for cand in PG_BIN_CANDIDATES:
        if (cand / "psql.exe").is_file():
            return cand
    raise SystemExit(
        "PostgreSQL 16/17 não encontrado. Instale ou defina SATI_PG_RESTORE no .env"
    )


def _run_psql(pg_bin: Path, pg: dict, sql: str, database: str | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if pg["password"]:
        env["PGPASSWORD"] = pg["password"]
    cmd = [
        str(pg_bin / "psql.exe"),
        "-h", pg["host"],
        "-p", pg["port"],
        "-U", pg["user"],
        "-d", database or pg["database"],
        "-v", "ON_ERROR_STOP=1",
        "-c", sql,
    ]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _run_psql_file(pg_bin: Path, pg: dict, sql_file: Path, database: str) -> None:
    env = os.environ.copy()
    if pg["password"]:
        env["PGPASSWORD"] = pg["password"]
    cmd = [
        str(pg_bin / "psql.exe"),
        "-h", pg["host"],
        "-p", pg["port"],
        "-U", pg["user"],
        "-d", database,
        "-v", "ON_ERROR_STOP=1",
        "-f", str(sql_file),
    ]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"psql falhou: {sql_file.name}")


def _db_exists(pg_bin: Path, pg: dict, db_name: str) -> bool:
    r = _run_psql(
        pg_bin, pg,
        f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'",
        database="postgres",
    )
    return r.returncode == 0 and "1" in (r.stdout or "")


def _create_db(pg_bin: Path, pg: dict, db_name: str) -> None:
    if _db_exists(pg_bin, pg, db_name):
        print(f"  banco '{db_name}' já existe")
        return
    r = _run_psql(pg_bin, pg, f'CREATE DATABASE "{db_name}"', database="postgres")
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"Não foi possível criar banco {db_name}")
    print(f"  banco '{db_name}' criado")


def _schema_has_tables(pg_bin: Path, pg: dict, schema: str, sati_pg: dict) -> bool:
    r = _run_psql(
        pg_bin, sati_pg,
        f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{schema}'",
    )
    if r.returncode != 0:
        return False
    m = re.search(r"\s+(\d+)\s*", r.stdout or "")
    return bool(m and int(m.group(1)) > 10)


def _ensure_apartamento(pg_bin: Path, pg: dict, tenant_cfg: dict) -> None:
    apt_id = tenant_cfg["apartamento_id"]
    nome = tenant_cfg["label"]
    slug = tenant_cfg["slug"]
    schema = tenant_cfg["schema"]
    sql = f"""
    INSERT INTO apartamentos (id, nome_empresa, slug, status, data_criacao)
    VALUES ({apt_id}, '{nome.replace("'", "''")}', '{slug}', 'ativo', NOW()::text)
    ON CONFLICT (id) DO UPDATE SET
        nome_empresa = EXCLUDED.nome_empresa,
        slug = EXCLUDED.slug;
    SELECT setval(
        pg_get_serial_sequence('apartamentos', 'id'),
        GREATEST((SELECT COALESCE(MAX(id), 1) FROM apartamentos), {apt_id})
    );
    INSERT INTO configuracoes_robo (apartamento_id, chave, valor)
    VALUES ({apt_id}, 'USE_SATI_SOURCE', 'true'),
           ({apt_id}, 'SATI_SCHEMA', '{schema}')
    ON CONFLICT (apartamento_id, chave) DO UPDATE SET valor = EXCLUDED.valor;
    """
    r = _run_psql(pg_bin, pg, sql)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit("Falha ao inserir apartamento")
    print(f"  apartamento id={apt_id} ({nome}) schema={schema}")


def _patch_env_windows(pg_bin: Path, tenant_cfg: dict) -> None:
    """Garante chaves Windows no .env (não sobrescreve senhas)."""
    env_path = ROOT / ".env"
    if not env_path.is_file():
        print("  aviso: .env não existe — copie de .env.example")
        return

    apt = tenant_cfg["apartamento_id"]
    schema = tenant_cfg["schema"]
    pg_restore = str(pg_bin / "pg_restore.exe").replace("\\", "\\\\")

    updates = {
        "BIWEB_LOCAL_DEV": "1",
        "BIWEB_REQUIRE_TENANT_LINK": "0",
        "BIWEB_SKIP_LOGIN": "true",
        "BIWEB_IDLE_MONITOR": "false",
        "BIWEB_COLETA_COMPROVANTE_AUTO": "false",
        "FLASK_ENV": "development",
        "EXECUTION_MODE": "sync",
        "USE_SATI_SOURCE": "true",
        "SATI_SCHEMA": schema,
        "SATI_RESTORE_USE_SUDO_POSTGRES": "0",
        "BIWEB_TRANSPORTADORA_ID": str(apt),
        "BIWEB_AUTO_APT": str(apt),
        "SATI_PG_RESTORE": pg_restore,
    }

    lines = env_path.read_text(encoding="utf-8").splitlines()
    keys_done = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f'{key}={updates[key]}')
                keys_done.add(key)
                continue
        out.append(line)
    for key, val in updates.items():
        if key not in keys_done:
            out.append(f"{key}={val}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"  .env atualizado (tenant {tenant_cfg['slug']}, schema {schema})")


def _locate_zip(apt_id: int, schema: str) -> Path | None:
    for folder in (ROOT / "downloads" / str(apt_id), ROOT / "downloads" / "1"):
        for name in (f"SATI-{schema}-atual.zip", "SATI-c3332-atual.zip", "SATI-c2910-atual.zip"):
            p = folder / name
            if p.is_file():
                return p
        for p in sorted(folder.glob("SATI-*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_file():
                return p
    return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Setup dev Windows (PG + schema + restore SATI)")
    ap.add_argument("--tenant", default="transporte-brasil", choices=TENANTS.keys())
    ap.add_argument("--skip-restore", action="store_true")
    ap.add_argument("--force-restore", action="store_true")
    ap.add_argument("--sync-first", action="store_true")
    args = ap.parse_args()

    if args.sync_first:
        from scripts.sync_from_debian import main as sync_main

        sys.argv = ["sync_from_debian.py", "--tenant", args.tenant]
        sync_main()

    tenant_cfg = TENANTS[args.tenant]
    apt_id = tenant_cfg["apartamento_id"]
    schema = tenant_cfg["schema"]

    app_url = os.getenv("DATABASE_URL", "").strip()
    sati_url = os.getenv("SATI_DATABASE_URL", "").strip() or app_url
    if not app_url.startswith("postgresql"):
        raise SystemExit("Configure DATABASE_URL no .env (postgresql://...)")

    pg_bin = _find_pg_bin()
    print(f"PostgreSQL: {pg_bin}")

    app_pg = _parse_pg_url(app_url)
    sati_pg = _parse_pg_url(sati_url)

    print("\n1. Bancos PostgreSQL")
    admin_pg = {**app_pg, "database": "postgres"}
    _create_db(pg_bin, admin_pg, app_pg["database"])
    if sati_pg["database"] != app_pg["database"]:
        _create_db(pg_bin, admin_pg, sati_pg["database"])

    print("\n2. Schema app (tabelas BIWEB)")
    sql_app = ROOT / "migrations" / "sql_scripts" / "criar_tabelas_biweb_apartamento.sql"
    if not sql_app.is_file():
        raise SystemExit(f"SQL não encontrado: {sql_app}")
    _run_psql_file(pg_bin, app_pg, sql_app, app_pg["database"])
    print("  tabelas app OK")

    print("\n3. Apartamento / tenant local")
    _ensure_apartamento(pg_bin, app_pg, tenant_cfg)

    print("\n4. .env (modo dev Windows)")
    _patch_env_windows(pg_bin, tenant_cfg)
    load_dotenv(ROOT / ".env", override=True)

    if args.skip_restore:
        print("\nRestore SATI ignorado (--skip-restore)")
    else:
        print("\n5. Restore SATI")
        zip_path = _locate_zip(apt_id, schema)
        if not zip_path:
            print("  aviso: nenhum SATI-*.zip em downloads/")
            print("  rode: python scripts/sync_from_debian.py --tenant", args.tenant)
        elif _schema_has_tables(pg_bin, sati_pg, schema, sati_pg) and not args.force_restore:
            print(f"  schema {schema} já tem tabelas — use --force-restore para restaurar de novo")
        else:
            print(f"  restaurando {zip_path.name} → {sati_pg['database']}.{schema}")
            os.environ.setdefault("SATI_DATABASE_URL", sati_url)
            os.environ.setdefault("SATI_SCHEMA", schema)
            os.environ["SATI_RESTORE_USE_SUDO_POSTGRES"] = "0"
            os.environ["SATI_PG_RESTORE"] = str(pg_bin / "pg_restore.exe")
            from sati_integration.robos.sati_db_restore import processar_arquivo_zip_sati

            processar_arquivo_zip_sati(zip_path, apartamento_id=apt_id)
            print("  restore SATI concluído")

    print("\n" + "=" * 50)
    print("Ambiente Windows pronto.")
    print(f"  Tenant:  {tenant_cfg['label']} (apt {apt_id}, schema {schema})")
    print(f"  App DB:  {app_pg['database']}")
    print(f"  SATI DB: {sati_pg['database']}")
    print("\n  python run_dev.py  →  http://127.0.0.1:5000")
    print("\nApós testar, deploy no Debian:")
    print("  python scripts/deploy_debian.py --confirmar-deploy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
