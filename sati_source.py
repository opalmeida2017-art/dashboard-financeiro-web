"""Resolução de parâmetros e leitura de dados direto do schema SATI (c3332)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

import config
from sati_queries import SATI_QUERY_KEYS, build_sati_query

_TRUTHY = frozenset({"1", "true", "yes", "on", "s"})


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUTHY


def use_sati_source() -> bool:
    env = os.getenv("USE_SATI_SOURCE", "").strip().lower()
    if env in _TRUTHY:
        return True
    if env in ("0", "false", "no", "off"):
        return False
    if os.getenv("SATI_DATABASE_URL"):
        return True
    db_url = (os.getenv("DATABASE_URL") or "").lower()
    return "sat1_sati_is" in db_url


@lru_cache(maxsize=1)
def get_sati_engine() -> Engine:
    """
    Banco SATI (ex.: sat1_sati_is na porta 5433).
    Use SATI_DATABASE_URL no .env quando DATABASE_URL for outro banco (ex.: dashboard_db).
    """
    sati_url = os.getenv("SATI_DATABASE_URL", "").strip()
    if sati_url:
        return create_engine(sati_url)
    from database import engine as app_engine

    return app_engine


def sati_enabled_for_apartment(app_engine: Engine, apartamento_id: int) -> bool:
    if not use_sati_source():
        return False
    try:
        with app_engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT valor FROM configuracoes_robo
                    WHERE apartamento_id = :apt_id AND chave = 'USE_SATI_SOURCE'
                    LIMIT 1
                    """
                ),
                {"apt_id": apartamento_id},
            ).fetchone()
            if row is not None:
                return _is_truthy(row[0])
    except Exception:
        pass
    return use_sati_source()


def is_sati_data_table(table_name: str, apartamento_id: int | None = None) -> bool:
    if table_name not in SATI_QUERY_KEYS:
        return False
    if apartamento_id is None:
        return use_sati_source()
    from database import engine as app_engine

    return sati_enabled_for_apartment(app_engine, apartamento_id)


def get_sati_schema() -> str:
    return os.getenv("SATI_SCHEMA", getattr(config, "SATI_SCHEMA", "c3332"))


def resolve_cod_filial(engine, apartamento_id: int) -> int | None:
    """Filial SATI opcional: configuracoes_robo.SATI_COD_FILIAL ou env SATI_COD_FILIAL."""
    env_val = os.getenv("SATI_COD_FILIAL", "").strip()
    if env_val.isdigit():
        return int(env_val)

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT valor FROM configuracoes_robo
                    WHERE apartamento_id = :apt_id AND chave = 'SATI_COD_FILIAL'
                    LIMIT 1
                    """
                ),
                {"apt_id": apartamento_id},
            ).fetchone()
            if row and row[0] and str(row[0]).strip().isdigit():
                return int(str(row[0]).strip())
    except Exception:
        pass
    return None


def fetch_sati_dataframe(app_engine: Engine, table_name: str, apartamento_id: int):
    import pandas as pd

    sql = build_sati_query(table_name, get_sati_schema())
    if not sql:
        return pd.DataFrame()

    cod_filial = resolve_cod_filial(app_engine, apartamento_id)
    params: dict[str, Any] = {
        "apartamento_id": apartamento_id,
        "cod_filial": cod_filial,
    }

    sati_engine = get_sati_engine()
    with sati_engine.connect() as conn:
        df = pd.read_sql_query(text(sql), conn, params=params)
    df.columns = [str(col).strip() for col in df.columns]
    return df
