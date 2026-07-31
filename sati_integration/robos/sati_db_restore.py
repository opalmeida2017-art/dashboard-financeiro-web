"""Download, extração e restore do dump SATI (SATI-c2910-atual.zip) no PostgreSQL."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from contextlib import contextmanager
from dotenv import load_dotenv

try:
    load_dotenv()
except (PermissionError, OSError):
    pass

_TABELAS_OBRIGATORIAS = (
    "conhecimento",
    "veiculo",
    "nota",
    "itemnota",
    "filial",
    "cliente",
    "motorista",
)

_MIN_TABELAS_PRE_DATA = int(os.getenv("SATI_RESTORE_MIN_TABELAS", "50"))


def _restore_lock_path(apartamento_id: int | None = None) -> Path:
    if apartamento_id is not None:
        try:
            from app.utils.paths import downloads_dir

            return downloads_dir(int(apartamento_id)) / "sati_restore.lock"
        except Exception:
            local_downloads = Path(__file__).resolve().parents[1] / "downloads" / str(
                int(apartamento_id)
            )
            local_downloads.mkdir(parents=True, exist_ok=True)
            return local_downloads / "sati_restore.lock"
    tenant_path = os.getenv("BI_TENANT_DIR", "").strip()
    if tenant_path:
        try:
            from infra.tenant_licensing.bi_tenant_runtime import ensure_tenant_runtime_dirs

            slug = os.getenv("BI_TENANT_SLUG", "").strip().lower()
            if slug:
                tenant_path = str(ensure_tenant_runtime_dirs(slug, tenant_path))
                os.environ["BI_TENANT_DIR"] = tenant_path
        except Exception:
            pass
        return Path(tenant_path) / "sati_restore.lock"
    try:
        from app.utils.paths import data_root

        return data_root() / "sati_restore.lock"
    except Exception:
        return Path("sati_restore.lock")


@contextmanager
def _restore_lock(apartamento_id: int | None):
    """Evita restore duplo (Flask debug) e sinaliza painel para aguardar."""
    lock = _restore_lock_path(apartamento_id)
    if lock.exists():
        raise RuntimeError(
            "Outra atualização do banco SATI já está em andamento. "
            "Aguarde terminar antes de abrir o painel."
        )
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("running", encoding="utf-8")
    os.environ["BIWEB_SATI_RESTORING"] = "1"
    try:
        yield
    finally:
        os.environ.pop("BIWEB_SATI_RESTORING", None)
        lock.unlink(missing_ok=True)


def _log(apartamento_id: int | None, msg: str) -> None:
    print(msg)
    if apartamento_id is not None:
        try:
            from app.data import database as db

            db.logar_progresso(apartamento_id, msg)
        except Exception:
            pass


def _schema_sql(name: str, default: str = "c3332") -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "", (name or "").strip()) or default


def _parse_pg_url(url: str) -> dict:
    u = urlparse(url)
    return {
        "host": u.hostname or "localhost",
        "port": str(u.port or 5432),
        "user": u.username or "postgres",
        "password": u.password or "",
        "database": (u.path or "/").lstrip("/") or "postgres",
    }


def _usar_postgres_sudo() -> bool:
    flag = os.getenv("SATI_RESTORE_USE_SUDO_POSTGRES", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    sati_url = os.getenv("SATI_DATABASE_URL", "").strip()
    if sati_url:
        db_name = sati_url.rstrip("/").split("/")[-1].lower()
        if db_name.startswith("bi_"):
            return False
    if flag in ("1", "true", "yes", "on"):
        return True
    if sys.platform.startswith("linux"):
        return bool(sati_url and "webadmin" in sati_url)
    return False


def _usuario_existe(nome: str) -> bool:
    if not nome or sys.platform == "win32":
        return False
    try:
        import pwd

        pwd.getpwnam(nome)
        return True
    except Exception:
        return False


def _pg_major_from_path(path: str) -> int:
    m = re.search(r"PostgreSQL[/\\](\d+)", path.replace("\\", "/"), re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"/postgresql/(\d+)/bin/", path.replace("\\", "/"), re.I)
    return int(m.group(1)) if m else 0


def _pg_restore_major(path: str) -> int:
    mv = _pg_major_from_path(path)
    if mv >= 16:
        return mv
    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        m = re.search(r"PostgreSQL[^\d]*(\d+)", out, re.I)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return mv


def _find_pg_restore() -> str:
    instalados: list[tuple[int, str]] = []
    for ver in ("17", "16", "15", "14", "13"):
        win = Path(f"C:/Program Files/PostgreSQL/{ver}/bin/pg_restore.exe")
        if win.exists():
            instalados.append((int(ver), str(win)))

    for ver in ("17", "16", "15"):
        linux = Path(f"/usr/lib/postgresql/{ver}/bin/pg_restore")
        if linux.is_file():
            instalados.append((int(ver), str(linux)))

    for p in ("/usr/bin/pg_restore", "/usr/local/bin/pg_restore"):
        if Path(p).is_file():
            instalados.append((_pg_restore_major(p), p))

    for name in ("pg_restore", "pg_restore.exe"):
        found = shutil.which(name)
        if found:
            instalados.append((_pg_restore_major(found), found))

    custom = os.getenv("SATI_PG_RESTORE", "").strip()
    if custom and Path(custom).exists():
        cv = _pg_restore_major(custom)
        instalados.append((cv or 14, custom))

    if not instalados:
        raise FileNotFoundError(
            "pg_restore não encontrado. Instale PostgreSQL 16 ou 17 e defina "
            "SATI_PG_RESTORE no .env."
        )

    best_ver, best_path = max(instalados, key=lambda x: x[0])
    if best_ver < 16:
        raise FileNotFoundError(
            f"O dump do SATI exige PostgreSQL 16+. Encontrado pg_restore {best_ver} em {best_path}."
        )

    custom = os.getenv("SATI_PG_RESTORE", "").strip()
    if custom and Path(custom).exists():
        cv = _pg_restore_major(custom)
        if cv >= 16 and cv >= best_ver:
            return custom

    return best_path


def extrair_zip_dump(zip_path: Path, destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(destino)

    dumps = list(destino.rglob("*.dump")) + list(destino.rglob("*.backup"))
    if not dumps:
        raise FileNotFoundError(f"Nenhum arquivo .dump encontrado dentro de {zip_path.name}")

    dumps.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dumps[0]


def _tmpdir_restore() -> Path:
    """Pasta com espaço para extrair dump (evita /tmp cheio no Debian)."""
    for cand in (
        os.getenv("SATI_RESTORE_TMPDIR", "").strip(),
        "/home/oitamar/tmp_sati",
        "/var/tmp",
        "/tmp",
    ):
        if not cand:
            continue
        p = Path(cand)
        try:
            p.mkdir(parents=True, exist_ok=True)
            test = p / f".sati_write_test_{uuid.uuid4().hex}"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
            return p
        except OSError:
            continue
    return Path(tempfile.gettempdir())


def _schema_de_nome_arquivo(nome: str) -> str | None:
    m = re.search(r"SATI-([a-zA-Z]\w*)-atual", nome, re.I)
    if m:
        return _schema_sql(m.group(1))
    m = re.search(r"SATI-([a-zA-Z]\w*)\.", nome, re.I)
    if m:
        return _schema_sql(m.group(1))
    return None


def _detectar_schema_dump_lista(
    pg_restore: str, pg: dict, dump_path: Path, usar_sudo: bool
) -> str | None:
    if usar_sudo:
        cmd = ["sudo", "-n", "-u", "postgres", pg_restore, "--list", str(dump_path)]
        env = os.environ.copy()
    else:
        cmd = [
            pg_restore,
            "-h",
            pg["host"],
            "-p",
            pg["port"],
            "-U",
            pg["user"],
            "-d",
            pg["database"],
            "--list",
            str(dump_path),
        ]
        env = os.environ.copy()
        if pg["password"]:
            env["PGPASSWORD"] = pg["password"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
        out = (proc.stdout or "") + (proc.stderr or "")
        for line in out.splitlines():
            m = re.search(r"SCHEMA\s+-?\s*(\S+)", line, re.I)
            if m:
                cand = _schema_sql(m.group(1))
                if cand and cand not in ("public", "pg_catalog"):
                    return cand
    except Exception:
        pass
    return None


def _resolver_schema_dump(
    dump_path: Path, pg_restore: str, pg: dict, usar_sudo: bool
) -> str:
    """Nome do schema no dump (ex.: c2910 do SATI-c2910-atual.zip)."""
    nome = _schema_sql(os.getenv("SATI_DUMP_SCHEMA", ""), "")
    if not nome:
        nome = _schema_de_nome_arquivo(dump_path.name) or ""
    if not nome:
        nome = _detectar_schema_dump_lista(pg_restore, pg, dump_path, usar_sudo) or ""
    if not nome:
        nome = _schema_sql(os.getenv("SATI_SCHEMA", "c3332"))
    return nome


def _sql_engine(sati_url: str):
    from sqlalchemy import create_engine

    return create_engine(sati_url)


def _executar_sql_autocommit(
    sati_url: str,
    sql: str,
    pg: dict | None = None,
    usar_sudo: bool = False,
) -> None:
    if usar_sudo and pg:
        proc = subprocess.run(
            [
                "sudo",
                "-n",
                "-u",
                "postgres",
                "psql",
                "-d",
                pg["database"],
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                sql,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(err or "psql falhou")
        return

    from sqlalchemy import text

    eng = _sql_engine(sati_url)
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(sql))


def _contar_tabelas_schema(
    sati_url: str,
    schema: str,
    pg: dict | None = None,
    usar_sudo: bool = False,
) -> int:
    schema_sql = _schema_sql(schema)
    if usar_sudo and pg:
        proc = subprocess.run(
            [
                "sudo",
                "-n",
                "-u",
                "postgres",
                "psql",
                "-d",
                pg["database"],
                "-tAc",
                (
                    "SELECT COUNT(*) FROM information_schema.tables "
                    f"WHERE table_schema = '{schema_sql}' AND table_type = 'BASE TABLE'"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode == 0:
            try:
                return int((proc.stdout or "0").strip())
            except ValueError:
                pass

    from sqlalchemy import text

    eng = _sql_engine(sati_url)
    with eng.connect() as conn:
        n = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = :schema AND table_type = 'BASE TABLE'
                """
            ),
            {"schema": schema_sql},
        ).scalar()
    return int(n or 0)


def _limpar_dominios_public_espelhados(
    sati_url: str,
    schema: str,
    apartamento_id: int | None,
    pg: dict,
    usar_sudo: bool,
) -> None:
    """Remove domínios espelhados em public antes de apagar o schema SATI."""
    schema_sql = _schema_sql(schema)
    sql = f"""
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN
            SELECT t.typname AS n
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = '{schema_sql}' AND t.typtype = 'd'
          LOOP
            BEGIN
              EXECUTE format('DROP DOMAIN IF EXISTS public.%I CASCADE', r.n);
            EXCEPTION WHEN undefined_object THEN
              NULL;
            END;
          END LOOP;
        END $$;
        """
    try:
        _executar_sql_autocommit(sati_url, sql, pg, usar_sudo)
        _log(apartamento_id, f"Domínios public espelhados de {schema_sql} removidos.")
    except Exception as exc:
        _log(apartamento_id, f"Aviso: limpeza domínios public ({schema_sql}): {exc}")


def _limpar_dominios_public_dom_globais(
    sati_url: str,
    apartamento_id: int | None,
    pg: dict,
    usar_sudo: bool,
) -> None:
    """Remove domínios dom_* em public (resíduo de restores anteriores / outros schemas)."""
    sql = """
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN
            SELECT t.typname AS n
            FROM pg_type t
            JOIN pg_namespace ns ON ns.oid = t.typnamespace
            WHERE ns.nspname = 'public' AND t.typtype = 'd' AND t.typname LIKE 'dom_%'
          LOOP
            EXECUTE format('DROP DOMAIN IF EXISTS public.%I CASCADE', r.n);
          END LOOP;
        END $$;
        """
    try:
        _executar_sql_autocommit(sati_url, sql, pg, usar_sudo)
        _log(apartamento_id, "Domínios public.dom_* removidos antes do restore.")
    except Exception as exc:
        _log(apartamento_id, f"Aviso: limpeza domínios public.dom_*: {exc}")


def _garantir_schema_vazio(
    sati_url: str,
    schema: str,
    apartamento_id: int | None,
    pg: dict,
    usar_sudo: bool,
    *,
    remover: bool = True,
) -> None:
    schema_sql = _schema_sql(schema)
    if not remover:
        _executar_sql_autocommit(
            sati_url,
            f'CREATE SCHEMA IF NOT EXISTS "{schema_sql}"',
            pg,
            usar_sudo,
        )
        _log(apartamento_id, f"Schema SATI {schema_sql} garantido (vazio até o restore).")
        return

    _executar_sql_autocommit(
        sati_url,
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND pid <> pg_backend_pid()
        """,
        pg,
        usar_sudo,
    )
    _limpar_dominios_public_espelhados(sati_url, schema_sql, apartamento_id, pg, usar_sudo)
    _limpar_dominios_public_dom_globais(sati_url, apartamento_id, pg, usar_sudo)
    _executar_sql_autocommit(
        sati_url,
        f'DROP SCHEMA IF EXISTS "{schema_sql}" CASCADE',
        pg,
        usar_sudo,
    )
    _log(
        apartamento_id,
        f"Schema {schema_sql} removido — carga limpa (evita COPY com chaves duplicadas).",
    )


def garantir_schema_sati_vazio(
    schema: str,
    apartamento_id: int | None = None,
) -> None:
    """API pública: remove schema SATI e recria vazio (painel de licenças / novo cliente)."""
    sati_url = os.getenv("SATI_DATABASE_URL", "").strip()
    if not sati_url:
        raise ValueError("SATI_DATABASE_URL não está definida no .env")

    pg = _parse_pg_url(sati_url)
    usar_sudo = _usar_postgres_sudo()
    schema_sql = _schema_sql(schema)
    if not schema_sql:
        raise ValueError("Schema SATI inválido")

    _garantir_schema_vazio(
        sati_url, schema_sql, apartamento_id, pg, usar_sudo, remover=True
    )
    _log(apartamento_id, f"Schema SATI {schema_sql} garantido vazio para importação.")


def _remover_funcoes_schema(
    sati_url: str,
    schema: str,
    apartamento_id: int | None,
    pg: dict,
    usar_sudo: bool,
) -> None:
    """Remove funções do schema para o 2º pre-data não falhar por 'já existe'."""
    schema_sql = _schema_sql(schema)
    sql = f"""
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN
            SELECT format(
              '%I.%I(%s)',
              n.nspname,
              p.proname,
              pg_catalog.pg_get_function_identity_arguments(p.oid)
            ) AS sig
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = '{schema_sql}'
          LOOP
            EXECUTE 'DROP FUNCTION IF EXISTS ' || r.sig || ' CASCADE';
          END LOOP;
        END $$;
        """
    _executar_sql_autocommit(sati_url, sql, pg, usar_sudo)
    _log(apartamento_id, f"Funções removidas de {schema_sql} (2º pre-data).")


def _remover_tabelas_parciais_schema(
    sati_url: str,
    schema: str,
    apartamento_id: int | None,
    pg: dict,
    usar_sudo: bool,
) -> None:
    schema_sql = _schema_sql(schema)
    sql = f"""
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN
            SELECT tablename FROM pg_tables WHERE schemaname = '{schema_sql}'
          LOOP
            EXECUTE format('DROP TABLE IF EXISTS {schema_sql}.%I CASCADE', r.tablename);
          END LOOP;
          FOR r IN
            SELECT sequence_name FROM information_schema.sequences
            WHERE sequence_schema = '{schema_sql}'
          LOOP
            EXECUTE format('DROP SEQUENCE IF EXISTS {schema_sql}.%I CASCADE', r.sequence_name);
          END LOOP;
        END $$;
        """
    _executar_sql_autocommit(sati_url, sql, pg, usar_sudo)
    _log(
        apartamento_id,
        f"Tabelas/sequências parciais removidas de {schema_sql} (domínios mantidos).",
    )


def _espelhar_dominios_public(
    sati_url: str,
    schema: str,
    apartamento_id: int | None,
    pg: dict,
    usar_sudo: bool,
) -> None:
    schema_sql = _schema_sql(schema)
    sql = f"""
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN
            SELECT t.typname AS n
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = '{schema_sql}' AND t.typtype = 'd'
          LOOP
            BEGIN
              EXECUTE format('CREATE DOMAIN public.%I AS {schema_sql}.%I', r.n, r.n);
            EXCEPTION WHEN duplicate_object THEN
              NULL;
            END;
          END LOOP;
        END $$;
        """
    _executar_sql_autocommit(sati_url, sql, pg, usar_sudo)
    _log(apartamento_id, f"Domínios {schema_sql} espelhados em public.")


def _conceder_schema_usuario_app(
    sati_url: str,
    schema: str,
    pg_user: str,
    apartamento_id: int | None,
    pg: dict,
    usar_sudo: bool,
) -> None:
    if not pg_user or pg_user in ("postgres", "root"):
        return
    schema_sql = _schema_sql(schema)
    user_sql = re.sub(r"[^a-zA-Z0-9_]", "", pg_user)
    if not user_sql:
        return
    sql = f"""
        GRANT USAGE ON SCHEMA "{schema_sql}" TO "{user_sql}";
        GRANT SELECT ON ALL TABLES IN SCHEMA "{schema_sql}" TO "{user_sql}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema_sql}"
            GRANT SELECT ON TABLES TO "{user_sql}";
        """
    try:
        _executar_sql_autocommit(sati_url, sql, pg, usar_sudo)
        _log(apartamento_id, f"Permissões do schema {schema_sql} concedidas a {user_sql}.")
    except Exception as exc:
        _log(apartamento_id, f"Aviso: não foi possível conceder permissões a {user_sql}: {exc}")


def _dump_path_para_restore(
    dump_path: Path, usar_sudo: bool, apartamento_id: int | None
) -> Path:
    if not usar_sudo:
        return dump_path
    # postgres precisa ler o arquivo: /var/tmp com modo 644 (home/oitamar é 750).
    dest = Path(f"/var/tmp/sati_{uuid.uuid4().hex}_{dump_path.name}")
    shutil.copy2(dump_path, dest)
    os.chmod(dest, 0o644)
    _log(apartamento_id, f"Dump copiado para {dest} (leitura postgres).")
    return dest


def _montar_comando_pg_restore(
    pg_restore: str,
    pg: dict,
    dump_path: Path,
    extra: list[str],
    usar_sudo: bool,
) -> tuple[list[str], dict]:
    env = os.environ.copy()
    if usar_sudo:
        cmd = ["sudo", "-n", "-u", "postgres", pg_restore, "-d", pg["database"], "--no-owner", "--no-acl"]
        cmd.extend(extra)
        cmd.append(str(dump_path))
        return cmd, env

    cmd = [
        pg_restore,
        "-h",
        pg["host"],
        "-p",
        pg["port"],
        "-U",
        pg["user"],
        "-d",
        pg["database"],
        "--no-owner",
        "--no-acl",
    ]
    cmd.extend(extra)
    cmd.append(str(dump_path))
    if pg["password"]:
        env["PGPASSWORD"] = pg["password"]
    return cmd, env


def _executar_pg_restore(
    pg_restore: str,
    pg: dict,
    dump_path: Path,
    extra: list[str],
    label: str,
    apartamento_id: int | None,
    usar_sudo: bool,
    *,
    obrigatorio: bool = False,
) -> subprocess.CompletedProcess:
    cmd, env = _montar_comando_pg_restore(pg_restore, pg, dump_path, extra, usar_sudo)
    _log(apartamento_id, f"pg_restore {label}…")
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=int(os.getenv("SATI_RESTORE_TIMEOUT_SEC", "7200")),
    )
    if proc.returncode != 0:
        trecho = ((proc.stderr or "") + "\n" + (proc.stdout or ""))[-4000:]
        _log(apartamento_id, f"Aviso pg_restore {label}: código {proc.returncode}")
        if trecho.strip():
            for linha in trecho.strip().splitlines()[-8:]:
                _log(apartamento_id, f"  pg_restore> {linha[:300]}")
        if obrigatorio:
            raise RuntimeError(
                f"pg_restore ({label}) falhou (código {proc.returncode}).\n{trecho}"
            )
    return proc


def _verificar_tabelas_apos_restore(apartamento_id: int | None, schema: str) -> None:
    sati_url = os.getenv("SATI_DATABASE_URL", "").strip()
    if not sati_url:
        return
    from sqlalchemy import text

    schema_sql = _schema_sql(schema)
    eng = _sql_engine(sati_url)
    faltando = []
    with eng.connect() as conn:
        for tbl in _TABELAS_OBRIGATORIAS:
            ok = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = :schema AND table_name = :tbl
                    """
                ),
                {"schema": schema_sql, "tbl": tbl},
            ).first()
            if not ok:
                faltando.append(f"{schema_sql}.{tbl}")
        n_conh = conn.execute(
            text(f'SELECT COUNT(*) FROM "{schema_sql}".conhecimento')
        ).scalar()
        n_nota = conn.execute(
            text(f'SELECT COUNT(*) FROM "{schema_sql}".nota')
        ).scalar()
        n_item = conn.execute(
            text(f'SELECT COUNT(*) FROM "{schema_sql}".itemnota')
        ).scalar()
    _log(
        apartamento_id,
        f"Tabelas OK no schema {schema_sql}. conhecimento: {n_conh or 0}, "
        f"nota: {n_nota or 0}, itemnota: {n_item or 0} linhas.",
    )
    if faltando:
        raise RuntimeError(
            "Restore incompleto. Tabelas ausentes: "
            + ", ".join(faltando)
            + ". Rode a atualização novamente até concluir."
        )
    if int(n_conh or 0) > 0 and int(n_nota or 0) == 0:
        raise RuntimeError(
            f"Restore incompleto: schema {schema_sql} tem conhecimento mas nota/itemnota vazios. "
            "Despesas do painel não carregarão. Rode «Atualizar banco SATI» novamente."
        )


def restaurar_dump_sati(
    dump_path: Path,
    apartamento_id: int | None = None,
    schema: str | None = None,
) -> None:
    sati_url = os.getenv("SATI_DATABASE_URL", "").strip()
    if not sati_url:
        raise ValueError("SATI_DATABASE_URL não está definida no .env")

    pg = _parse_pg_url(sati_url)
    pg_restore = _find_pg_restore()
    usar_sudo = _usar_postgres_sudo()
    dump_path = Path(dump_path)

    dump_schema = _resolver_schema_dump(dump_path, pg_restore, pg, usar_sudo)
    if schema:
        dump_schema = _schema_sql(schema)

    _log(apartamento_id, f"Usando pg_restore: {pg_restore}")
    if usar_sudo:
        _log(apartamento_id, "Restore via superusuário postgres (sudo).")
    _log(
        apartamento_id,
        f"Restaurando dump no banco {pg['database']} (schema {dump_schema}) — "
        "não use o painel até aparecer 'Restore concluído'.",
    )

    dump_restore = _dump_path_para_restore(dump_path, usar_sudo, apartamento_id)

    with _restore_lock(apartamento_id):
        keep = os.getenv("SATI_RESTORE_KEEP_SCHEMA", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if not keep:
            _garantir_schema_vazio(
                sati_url, dump_schema, apartamento_id, pg, usar_sudo, remover=True
            )
        else:
            _garantir_schema_vazio(
                sati_url, dump_schema, apartamento_id, pg, usar_sudo, remover=False
            )

        # 1º pre-data: cria domínios no schema; tabelas/funções falham sem public.dom_*.
        _executar_pg_restore(
            pg_restore,
            pg,
            dump_restore,
            ["--section=pre-data"],
            "pre-data domínios (1/4)",
            apartamento_id,
            usar_sudo,
        )
        _espelhar_dominios_public(sati_url, dump_schema, apartamento_id, pg, usar_sudo)
        try:
            from sati_integration.db.sati_dominios_patch import aplicar_patch_restore

            aplicar_patch_restore(
                lambda sql: _executar_sql_autocommit(sati_url, sql, pg, usar_sudo),
                dump_schema,
                apartamento_id,
                _log,
            )
        except Exception as exc:
            _log(apartamento_id, f"Aviso patch domínios SATI: {exc}")
        _remover_funcoes_schema(sati_url, dump_schema, apartamento_id, pg, usar_sudo)

        # 2º pre-data: tabelas/funções usam public.dom_* espelhados.
        _executar_pg_restore(
            pg_restore,
            pg,
            dump_restore,
            ["--section=pre-data"],
            "pre-data tabelas (2/4)",
            apartamento_id,
            usar_sudo,
        )

        n_tab = _contar_tabelas_schema(sati_url, dump_schema, pg, usar_sudo)
        _log(apartamento_id, f"Tabelas em {dump_schema} após pre-data: {n_tab}")
        if n_tab < _MIN_TABELAS_PRE_DATA:
            raise RuntimeError(
                f"pre-data incompleto: apenas {n_tab} tabelas em {dump_schema}. "
                "Verifique domínios public, permissões postgres e SATI_RESTORE_USE_SUDO_POSTGRES=1."
            )

        _executar_pg_restore(
            pg_restore,
            pg,
            dump_restore,
            ["--section=data"],
            "data (3/4)",
            apartamento_id,
            usar_sudo,
            obrigatorio=True,
        )
        _executar_pg_restore(
            pg_restore,
            pg,
            dump_restore,
            ["--section=post-data"],
            "post-data (4/4)",
            apartamento_id,
            usar_sudo,
        )

        _conceder_schema_usuario_app(
            sati_url, dump_schema, pg["user"], apartamento_id, pg, usar_sudo
        )
        _verificar_tabelas_apos_restore(apartamento_id, dump_schema)
        try:
            from sati_integration.db.sati_km_vazio_patch import aplicar_patch_km_vazio_restore

            aplicar_patch_km_vazio_restore(
                lambda sql: _executar_sql_autocommit(sati_url, sql, pg, usar_sudo),
                dump_schema,
                apartamento_id,
                _log,
            )
        except Exception as exc:
            _log(apartamento_id, f"Aviso patch km vazio MDF-e: {exc}")

    if usar_sudo and dump_restore != dump_path and Path(dump_restore).exists():
        Path(dump_restore).unlink(missing_ok=True)

    _log(apartamento_id, "Restore do schema SATI concluído com sucesso.")


def processar_arquivo_zip_sati(
    zip_path: Path,
    apartamento_id: int | None = None,
    manter_extraido: bool = False,
) -> Path:
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {zip_path}")

    tmp_root = _tmpdir_restore() / f"sati_restore_{uuid.uuid4().hex}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    try:
        dump_path = extrair_zip_dump(zip_path, tmp_root / "extracted")
        _log(apartamento_id, f"Dump extraído: {dump_path.name}")
        restaurar_dump_sati(dump_path, apartamento_id=apartamento_id)
        if manter_extraido:
            dest = zip_path.parent / dump_path.name
            shutil.copy2(dump_path, dest)
            return dest
        return dump_path
    finally:
        if not manter_extraido:
            shutil.rmtree(tmp_root, ignore_errors=True)


def localizar_zip_baixado(pasta_downloads: str | Path) -> Path | None:
    pasta = Path(pasta_downloads)
    if not pasta.is_dir():
        return None

    padrao = os.getenv("SATI_ZIP_GLOB", "SATI*.zip")
    candidatos = sorted(pasta.glob(padrao), key=lambda p: p.stat().st_mtime, reverse=True)
    for c in candidatos:
        if c.is_file() and not c.name.endswith(".crdownload"):
            return c
    return None


def extrair_url_zip_do_html(html: str) -> str | None:
    m = re.search(r"https?://[^\s\"'<>]+SATI[^\s\"'<>]*\.zip", html, re.IGNORECASE)
    return m.group(0) if m else None
