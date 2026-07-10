"""
Snapshot BI — viagens com DRE pré-calculado (tabelas public.*).

Recalculado após import SATI; leitura aplica os mesmos filtros do painel em memória.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.data import database as db
from app.data import data_manager as dm
from app.core import dre_viagem as dre
from app.utils.dre_tenant_config import obter_dre_opts
from sati_integration.db.sati_source import sati_enabled_for_apartment

_SNAPSHOT_MEM: dict[int, tuple[float, pd.DataFrame]] = {}
_SNAPSHOT_MEM_TTL = int(os.environ.get("BIWEB_SNAPSHOT_MEM_TTL", "120"))
_BUILD_LOCK = threading.Lock()


def ensure_tables() -> None:
    """Cria tabelas se ainda não existirem (migration 8 ou bootstrap)."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS bi_snapshot_meta (
                    apartamento_id INTEGER PRIMARY KEY,
                    sati_generation TEXT,
                    status TEXT NOT NULL DEFAULT 'empty',
                    row_count INTEGER DEFAULT 0,
                    build_started_at TIMESTAMP,
                    rebuilt_at TIMESTAMP,
                    error_message TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS bi_viagem_dre (
                    apartamento_id INTEGER NOT NULL,
                    numero INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    dataviagemmotorista TIMESTAMP,
                    placaveiculo TEXT,
                    nomefilial TEXT,
                    codembarcador INTEGER,
                    veiculoproprio TEXT,
                    tipofrete TEXT,
                    nomeunidembarque TEXT,
                    PRIMARY KEY (apartamento_id, numero)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_bi_viagem_dre_apt_data
                ON bi_viagem_dre (apartamento_id, dataviagemmotorista)
                """
            )
        )


def _table_exists(name: str) -> bool:
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :t LIMIT 1"
                ),
                {"t": name},
            ).first()
            return row is not None
    except Exception:
        return False


def get_meta(apartamento_id: int) -> dict | None:
    if not _table_exists("bi_snapshot_meta"):
        return None
    with db.engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM bi_snapshot_meta WHERE apartamento_id = :id"),
            {"id": apartamento_id},
        ).mappings().first()
    return dict(row) if row else None


def snapshot_is_ready(apartamento_id: int) -> bool:
    if not sati_enabled_for_apartment(db.engine, apartamento_id):
        return False
    meta = get_meta(apartamento_id)
    return bool(meta and str(meta.get("status") or "").lower() == "ready" and (meta.get("row_count") or 0) > 0)


def snapshot_is_building(apartamento_id: int) -> bool:
    meta = get_meta(apartamento_id)
    return bool(meta and str(meta.get("status") or "").lower() == "building")


def _invalidate_mem(apartamento_id: int) -> None:
    _SNAPSHOT_MEM.pop(apartamento_id, None)


def _json_default(val: Any) -> Any:
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.isoformat()
    if isinstance(val, float) and pd.isna(val):
        return None
    return str(val)


def _serialize_row(row: dict) -> str:
    cleaned = {}
    for k, v in row.items():
        try:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                cleaned[k] = None
            elif isinstance(v, (pd.Timestamp, datetime)):
                cleaned[k] = v.isoformat()
            else:
                cleaned[k] = v
        except Exception:
            cleaned[k] = str(v)
    return json.dumps(cleaned, ensure_ascii=False)


def _coerce_snapshot_dates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    for col in ("dataviagemmotorista", "dataemissao", "datacontrole"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _index_cols_from_row(row: dict) -> dict:
    cm = {str(k).lower(): k for k in row.keys()}

    def g(*keys, default=None):
        for key in keys:
            orig = cm.get(key.lower())
            if orig is not None:
                return row.get(orig)
        return default

    dt = g("dataviagemmotorista", "dataemissao")
    try:
        dt_parsed = pd.to_datetime(dt, errors="coerce")
        dt_val = None if pd.isna(dt_parsed) else dt_parsed.to_pydatetime()
    except Exception:
        dt_val = None

    cod_emb = g("codembarcador", "codEmbarcador")
    try:
        cod_emb_i = int(float(cod_emb)) if cod_emb not in (None, "", 0) else None
    except (TypeError, ValueError):
        cod_emb_i = None

    num = g("numero")
    try:
        num_i = int(float(num)) if num is not None else None
    except (TypeError, ValueError):
        num_i = None

    return {
        "numero": num_i,
        "dataviagemmotorista": dt_val,
        "placaveiculo": str(g("placaveiculo", "placa") or "").strip().upper() or None,
        "nomefilial": str(g("nomefilial", "nomefil") or "").strip() or None,
        "codembarcador": cod_emb_i,
        "veiculoproprio": str(g("veiculoproprio") or "").strip().upper() or None,
        "tipofrete": str(g("tipofrete") or "").strip().upper() or None,
        "nomeunidembarque": str(g("nomeunidembarque") or "").strip() or None,
    }


def load_viagens_dre_dataframe(apartamento_id: int) -> pd.DataFrame | None:
    """Carrega todas as viagens materializadas do apartamento (com DRE)."""
    if not snapshot_is_ready(apartamento_id):
        return None

    now = time.time()
    cached = _SNAPSHOT_MEM.get(apartamento_id)
    if cached and (now - cached[0]) < _SNAPSHOT_MEM_TTL:
        return cached[1].copy()

    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT data_json FROM bi_viagem_dre "
                "WHERE apartamento_id = :id ORDER BY numero"
            ),
            {"id": apartamento_id},
        ).fetchall()

    if not rows:
        return None

    records = [json.loads(r[0]) for r in rows]
    df = _coerce_snapshot_dates(pd.DataFrame(records))
    _SNAPSHOT_MEM[apartamento_id] = (now, df)
    return df.copy()


def filtrar_viagens_snapshot(
    df: pd.DataFrame,
    start_date: datetime | None,
    end_date: datetime | None,
    placa_filter: str,
    filial_filter: list,
    tipo_negocio_filter: str,
    unidade_embarque_filter: list | None = None,
    embarcador_filter: str = "Todos",
) -> pd.DataFrame:
    """Mesma cadeia de filtros usada em _obter_dados_filtrados_mestre."""
    if df is None or df.empty:
        return pd.DataFrame()
    col_map = dm._get_case_insensitive_column_map(df.columns)
    out = df
    if tipo_negocio_filter and tipo_negocio_filter != "Todos":
        out = dm._filtrar_viagens_por_tipo_negocio(out, col_map, tipo_negocio_filter)
    out = dm.apply_filters_to_df(
        out,
        start_date,
        end_date,
        placa_filter,
        filial_filter,
        unidade_embarque_filter,
    )
    return dm._aplicar_filtro_embarcador(out, embarcador_filter)


def _fat_from_viagens(df_viagens: pd.DataFrame) -> pd.DataFrame:
    """Subset faturamento a partir das viagens já filtradas."""
    if df_viagens.empty:
        return pd.DataFrame()
    cv = dm._get_case_insensitive_column_map(df_viagens.columns)
    cols = []
    for key in (
        "numero",
        "numconhec",
        "dataviagemmotorista",
        "freteempresa",
        "fretemotorista",
        "permitefaturar",
        "pagarconhecimento",
        "codfilial",
        "codembarcador",
        "nomeembarcador",
        "placaveiculo",
        "nomefilial",
    ):
        if key in cv:
            cols.append(cv[key])
    if "numero" not in cv:
        return pd.DataFrame()
    df = df_viagens[cols].drop_duplicates(subset=[cv["numero"]]).copy()
    if "permitefaturar" in cv:
        df = df[df[cv["permitefaturar"]].astype(str).str.upper().str.strip() == "S"]
    return df


def _set_meta(apartamento_id: int, **fields) -> None:
    ensure_tables()
    meta = get_meta(apartamento_id) or {"apartamento_id": apartamento_id}
    meta.update(fields)
    meta["apartamento_id"] = apartamento_id
    cols = [
        "apartamento_id",
        "sati_generation",
        "status",
        "row_count",
        "build_started_at",
        "rebuilt_at",
        "error_message",
    ]
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO bi_snapshot_meta (
                    apartamento_id, sati_generation, status, row_count,
                    build_started_at, rebuilt_at, error_message
                ) VALUES (
                    :apartamento_id, :sati_generation, :status, :row_count,
                    :build_started_at, :rebuilt_at, :error_message
                )
                ON CONFLICT (apartamento_id) DO UPDATE SET
                    sati_generation = EXCLUDED.sati_generation,
                    status = EXCLUDED.status,
                    row_count = EXCLUDED.row_count,
                    build_started_at = EXCLUDED.build_started_at,
                    rebuilt_at = EXCLUDED.rebuilt_at,
                    error_message = EXCLUDED.error_message
                """
            ),
            {k: meta.get(k) for k in cols},
        )


def rebuild_bi_viagem_snapshot(
    apartamento_id: int,
    sati_generation: str | None = None,
) -> int:
    """
    Recalcula snapshot completo (sem filtro de data) e grava em bi_viagem_dre.
    Retorna quantidade de linhas gravadas.
    """
    if not sati_enabled_for_apartment(db.engine, apartamento_id):
        return 0

    with _BUILD_LOCK:
        ensure_tables()
        generation = sati_generation or datetime.now().strftime("%Y%m%d%H%M%S")
        _set_meta(
            apartamento_id,
            status="building",
            sati_generation=generation,
            build_started_at=datetime.now(),
            error_message=None,
            row_count=0,
        )
        _invalidate_mem(apartamento_id)

        try:
            db.logar_progresso(
                apartamento_id,
                "BI snapshot: carregando viagens do SATI (período completo)...",
            )
            df_v = dm.get_data_as_dataframe(
                "relFilViagensCliente", apartamento_id, None, None
            )
            df_acerto = dm.get_data_as_dataframe(
                "relFilAcertoMot", apartamento_id, None, None
            )
            if df_v.empty:
                _set_meta(
                    apartamento_id,
                    status="ready",
                    row_count=0,
                    rebuilt_at=datetime.now(),
                    error_message=None,
                )
                return 0

            cv = dm._get_case_insensitive_column_map(df_v.columns)
            dre_opts = obter_dre_opts(apartamento_id)
            campo_rec = dre_opts.get("campo_receita", "freteempresa")
            col_filtro = cv.get(campo_rec) or cv.get("freteempresa")
            if col_filtro:
                df_work = df_v[
                    pd.to_numeric(df_v[col_filtro], errors="coerce").fillna(0) > 0
                ].copy()
            else:
                df_work = df_v.copy()

            db.logar_progresso(
                apartamento_id,
                f"BI snapshot: calculando DRE em {len(df_work)} viagem(ns)...",
            )
            df_dre = dre.aplicar_dre_em_dataframe(df_work, df_acerto, dre_opts=dre_opts)

            with db.engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM bi_viagem_dre WHERE apartamento_id = :id"),
                    {"id": apartamento_id},
                )
                batch = []
                for row in df_dre.to_dict("records"):
                    idx = _index_cols_from_row(row)
                    num = idx.get("numero")
                    if num is None:
                        continue
                    batch.append(
                        {
                            "apartamento_id": apartamento_id,
                            "numero": num,
                            "data_json": _serialize_row(row),
                            **{k: v for k, v in idx.items() if k != "numero"},
                        }
                    )
                    if len(batch) >= 500:
                        conn.execute(
                            text(
                                """
                                INSERT INTO bi_viagem_dre (
                                    apartamento_id, numero, data_json,
                                    dataviagemmotorista, placaveiculo, nomefilial,
                                    codembarcador, veiculoproprio, tipofrete, nomeunidembarque
                                ) VALUES (
                                    :apartamento_id, :numero, :data_json,
                                    :dataviagemmotorista, :placaveiculo, :nomefilial,
                                    :codembarcador, :veiculoproprio, :tipofrete, :nomeunidembarque
                                )
                                """
                            ),
                            batch,
                        )
                        batch.clear()
                if batch:
                    conn.execute(
                        text(
                            """
                            INSERT INTO bi_viagem_dre (
                                apartamento_id, numero, data_json,
                                dataviagemmotorista, placaveiculo, nomefilial,
                                codembarcador, veiculoproprio, tipofrete, nomeunidembarque
                            ) VALUES (
                                :apartamento_id, :numero, :data_json,
                                :dataviagemmotorista, :placaveiculo, :nomefilial,
                                :codembarcador, :veiculoproprio, :tipofrete, :nomeunidembarque
                            )
                            """
                        ),
                        batch,
                    )

            n = len(df_dre)
            _set_meta(
                apartamento_id,
                status="ready",
                row_count=n,
                rebuilt_at=datetime.now(),
                error_message=None,
            )
            _invalidate_mem(apartamento_id)
            db.logar_progresso(
                apartamento_id,
                f"BI snapshot pronto: {n} viagem(ns) materializada(s).",
            )
            return n
        except Exception as exc:
            _set_meta(
                apartamento_id,
                status="error",
                error_message=str(exc)[:2000],
                rebuilt_at=datetime.now(),
            )
            _invalidate_mem(apartamento_id)
            db.logar_progresso(apartamento_id, f"ERRO BI snapshot: {exc}")
            raise


def invalidate_snapshot(apartamento_id: int) -> None:
    """Marca snapshot inválido (início do restore SATI)."""
    ensure_tables()
    with db.engine.begin() as conn:
        conn.execute(
            text("DELETE FROM bi_viagem_dre WHERE apartamento_id = :id"),
            {"id": apartamento_id},
        )
    _set_meta(
        apartamento_id,
        status="building",
        row_count=0,
        build_started_at=datetime.now(),
        error_message=None,
    )
    _invalidate_mem(apartamento_id)


def enqueue_rebuild_bi_snapshot(apartamento_id: int, sati_generation: str | None = None) -> bool:
    """Enfileira rebuild no RQ; se Redis indisponível, executa em thread."""
    try:
        import redis
        from rq import Queue

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        conn = redis.from_url(redis_url)
        q = Queue("default", connection=conn)
        q.enqueue(
            "app.core.logic.rebuild_bi_snapshot_job",
            apartamento_id,
            sati_generation,
            job_timeout=7200,
        )
        return True
    except Exception:
        pass

    def _run():
        try:
            from app import app as flask_app

            with flask_app.app_context():
                rebuild_bi_viagem_snapshot(apartamento_id, sati_generation)
        except Exception as exc:
            print(f"BI snapshot (thread): {exc}")

    threading.Thread(target=_run, daemon=True).start()
    return False
