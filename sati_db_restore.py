"""Download, extração e restore do dump SATI (SATI-c3332-atual.zip) no PostgreSQL."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

_TABELAS_OBRIGATORIAS = (
    "conhecimento",
    "veiculo",
    "nota",
    "itemnota",
    "filial",
    "cliente",
    "motorista",
)


@contextmanager
def _restore_lock(apartamento_id: int | None):
    """Evita restore duplo (Flask debug) e sinaliza painel para aguardar."""
    try:
        from biweb_paths import data_root
    except Exception:
        yield
        return

    lock = data_root() / "sati_restore.lock"
    if lock.exists():
        raise RuntimeError(
            "Outra atualização do banco SATI já está em andamento. "
            "Aguarde terminar antes de abrir o painel."
        )
    lock.write_text("running", encoding="utf-8")
    os.environ["BIWEB_SATI_RESTORING"] = "1"
    try:
        yield
    finally:
        os.environ.pop("BIWEB_SATI_RESTORING", None)
        lock.unlink(missing_ok=True)


def _verificar_tabelas_apos_restore(apartamento_id: int | None, schema: str) -> None:
    sati_url = os.getenv("SATI_DATABASE_URL", "").strip()
    if not sati_url:
        return
    from sqlalchemy import create_engine, text

    eng = create_engine(sati_url)
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
                {"schema": schema, "tbl": tbl},
            ).first()
            if not ok:
                faltando.append(f"{schema}.{tbl}")
        n_conh = conn.execute(
            text(f'SELECT COUNT(*) FROM "{schema}".conhecimento')
        ).scalar()
    _log(apartamento_id, f"Tabelas OK no schema {schema}. conhecimento: {n_conh or 0} linhas.")
    if faltando:
        raise RuntimeError(
            "Restore incompleto. Tabelas ausentes: "
            + ", ".join(faltando)
            + ". Rode a atualização novamente até concluir."
        )


def _log(apartamento_id: int | None, msg: str) -> None:
    print(msg)
    if apartamento_id is not None:
        try:
            import database as db

            db.logar_progresso(apartamento_id, msg)
        except Exception:
            pass


def _parse_pg_url(url: str) -> dict:
    u = urlparse(url)
    return {
        "host": u.hostname or "localhost",
        "port": str(u.port or 5432),
        "user": u.username or "postgres",
        "password": u.password or "",
        "database": (u.path or "/").lstrip("/") or "postgres",
    }


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
    """
    Dump SATI atual usa formato 1.16+ → exige pg_restore do PostgreSQL 16 ou superior.
    """
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

    try:
        from embedded_pg import pg_restore_path

        p = pg_restore_path()
        if Path(p).exists():
            mv = _pg_restore_major(p) or 16
            instalados.append((mv, p))
    except Exception:
        pass

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
            "SATI_PG_RESTORE no .env (ex.: ...\\PostgreSQL\\17\\bin\\pg_restore.exe)."
        )

    best_ver, best_path = max(instalados, key=lambda x: x[0])
    if best_ver < 16:
        raise FileNotFoundError(
            f"O dump do SATI exige PostgreSQL 16+. Encontrado apenas pg_restore "
            f"versão {best_ver} em {best_path}. Instale PG 17 e atualize SATI_PG_RESTORE."
        )

    custom = os.getenv("SATI_PG_RESTORE", "").strip()
    if custom and Path(custom).exists():
        cv = _pg_restore_major(custom)
        if cv >= 16 and cv >= best_ver:
            return custom
        if cv and cv < 16:
            _log(
                None,
                f"Aviso: SATI_PG_RESTORE usa PG {cv}; usando PG {best_ver} "
                f"({best_path}) compatível com o dump.",
            )

    return best_path


def extrair_zip_dump(zip_path: Path, destino: Path) -> Path:
    """Extrai o .zip e retorna o caminho do arquivo .dump encontrado."""
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(destino)

    dumps = list(destino.rglob("*.dump")) + list(destino.rglob("*.backup"))
    if not dumps:
        raise FileNotFoundError(f"Nenhum arquivo .dump encontrado dentro de {zip_path.name}")

    dumps.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dumps[0]


def _preparar_banco_para_restore(
    sati_url: str, schema: str, apartamento_id: int | None
) -> None:
    """
    Apaga o schema do tenant antes do pg_restore.
    Sem isso, a etapa COPY (data) falha com chaves duplicadas na 2ª atualização.
    """
    if os.getenv("SATI_RESTORE_KEEP_SCHEMA", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        _log(apartamento_id, f"Mantendo schema {schema} (SATI_RESTORE_KEEP_SCHEMA=1).")
        return

    from sqlalchemy import create_engine, text

    schema_sql = re.sub(r"[^a-zA-Z0-9_]", "", schema) or "c3332"
    eng = create_engine(sati_url)
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
                """
            )
        )
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_sql}" CASCADE'))
    _log(
        apartamento_id,
        f"Schema {schema_sql} removido — carga limpa (evita COPY com chaves duplicadas).",
    )


def _espelhar_dominios_public(sati_url: str, schema: str, apartamento_id: int | None) -> None:
    """
    Dump SATI cria DOMAIN em c3332, mas tabelas referenciam public.dom_*.
    Copia os domínios para public antes de criar as tabelas.
    """
    from sqlalchemy import create_engine, text

    eng = create_engine(sati_url)
    schema_sql = re.sub(r"[^a-zA-Z0-9_]", "", schema) or "c3332"
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
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(sql))
    _log(apartamento_id, f"Domínios {schema} espelhados em public.")


def _restaurar_por_secoes(
    pg_restore: str,
    pg: dict,
    dump_path: Path,
    apartamento_id: int | None,
) -> None:
    """Restore SATI: pre-data → espelha domínios → pre-data/data/post-data."""
    env = os.environ.copy()
    if pg["password"]:
        env["PGPASSWORD"] = pg["password"]

    base = [
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

    def run_section(extra: list[str], label: str, fail_on_error: bool = False) -> None:
        cmd = base + extra + [str(dump_path)]
        _log(apartamento_id, f"pg_restore {label}…")
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("SATI_RESTORE_TIMEOUT_SEC", "7200")),
        )
        if fail_on_error and proc.returncode != 0:
            stderr = (proc.stderr or "")[-4000:]
            stdout = (proc.stdout or "")[-2000:]
            raise RuntimeError(
                f"pg_restore ({label}) falhou (código {proc.returncode}).\n{stderr}\n{stdout}"
            )

    run_section(["--section=pre-data"], "pre-data domínios (1/4)")


def restaurar_dump_sati(
    dump_path: Path,
    apartamento_id: int | None = None,
    schema: str | None = None,
) -> None:
    """Restaura o dump no banco configurado em SATI_DATABASE_URL."""
    sati_url = os.getenv("SATI_DATABASE_URL", "").strip()
    if not sati_url:
        raise ValueError("SATI_DATABASE_URL não está definida no .env")

    schema = (schema or os.getenv("SATI_SCHEMA", "c3332")).strip()
    pg = _parse_pg_url(sati_url)
    pg_restore = _find_pg_restore()
    _log(apartamento_id, f"Usando pg_restore: {pg_restore}")

    _log(
        apartamento_id,
        f"Restaurando dump no banco {pg['database']} (schema {schema}) — "
        "não use o painel até aparecer 'Restore concluído'.",
    )

    with _restore_lock(apartamento_id):
        _preparar_banco_para_restore(sati_url, schema, apartamento_id)
        _restaurar_por_secoes(pg_restore, pg, dump_path, apartamento_id)
        _espelhar_dominios_public(sati_url, schema, apartamento_id)

        env = os.environ.copy()
        if pg["password"]:
            env["PGPASSWORD"] = pg["password"]
        base = [
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
        for label, extra, strict in (
            ("pre-data tabelas (2/4)", ["--section=pre-data"], False),
            ("data (3/4)", ["--section=data"], True),
            ("post-data (4/4)", ["--section=post-data"], False),
        ):
            cmd = base + extra + [str(dump_path)]
            _log(apartamento_id, f"pg_restore {label}…")
            proc = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=int(os.getenv("SATI_RESTORE_TIMEOUT_SEC", "7200")),
            )
            if strict and proc.returncode != 0:
                raise RuntimeError(
                    f"pg_restore ({label}) falhou.\n{(proc.stderr or '')[-3000:]}"
                )

        _verificar_tabelas_apos_restore(apartamento_id, schema)

    _log(apartamento_id, "Restore do schema SATI concluído com sucesso.")


def processar_arquivo_zip_sati(
    zip_path: Path,
    apartamento_id: int | None = None,
    manter_extraido: bool = False,
) -> Path:
    """Extrai o zip e executa pg_restore. Retorna o caminho do .dump usado."""
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {zip_path}")

    tmp_root = Path(tempfile.mkdtemp(prefix="sati_restore_"))
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
    """Procura SATI-c3332-atual.zip (ou padrão SATI*.zip) na pasta de downloads."""
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
