"""Após restore SATI: calcula km vazio entre viagens e grava em conhecimento.kmvazio.

Regra por veículo (conhecimento.codveiculo), ordenado por dataviagemmotorista e número:
  km_vazio(viagem atual) = kmini(atual) − kmfim(viagem anterior)
  (somente se o resultado for > 0)

Também espelha o valor em manif.kmvazio (MDF-e ligado ao CT-e), quando existir.

Nota: manif.vazio no SATI é dom_resp (S/N), não quilometragem — usamos kmvazio (dom_quantreal).
"""

from __future__ import annotations

import re


def _schema_sql(schema: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "", (schema or "").strip()) or "c3332"


def sql_ensure_kmvazio_column(schema: str, table: str = "conhecimento") -> str:
    s = _schema_sql(schema)
    t = re.sub(r"[^a-zA-Z0-9_]", "", (table or "").strip()) or "conhecimento"
    return f"""
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = '{s}' AND table_name = '{t}' AND column_name = 'kmvazio'
  ) THEN
    EXECUTE format(
      'ALTER TABLE %I.%I ADD COLUMN kmvazio %I.dom_quantreal',
      '{s}', '{t}', '{s}'
    );
  END IF;
END $$;
"""


def sql_disable_table_triggers(schema: str, table: str) -> str:
    s = _schema_sql(schema)
    t = re.sub(r"[^a-zA-Z0-9_]", "", (table or "").strip())
    return f"ALTER TABLE {s}.{t} DISABLE TRIGGER USER"


def sql_enable_table_triggers(schema: str, table: str) -> str:
    s = _schema_sql(schema)
    t = re.sub(r"[^a-zA-Z0-9_]", "", (table or "").strip())
    return f"ALTER TABLE {s}.{t} ENABLE TRIGGER USER"


def sql_disable_manif_triggers(schema: str) -> str:
    return sql_disable_table_triggers(schema, "manif")


def sql_enable_manif_triggers(schema: str) -> str:
    return sql_enable_table_triggers(schema, "manif")


def sql_atualizar_km_vazio_conhecimentos(schema: str) -> str:
    """kmvazio no CT-e = kmini atual − kmfim da viagem anterior (mesmo veículo)."""
    s = _schema_sql(schema)
    return f"""
WITH viagens AS (
  SELECT
    c.numero,
    c.kmini::numeric AS kmini,
    LAG(c.kmfim::numeric) OVER (
      PARTITION BY c.codveiculo
      ORDER BY c.dataviagemmotorista NULLS LAST, c.numero
    ) AS prev_kmfim
  FROM {s}.conhecimento c
  WHERE c.cancelado IS DISTINCT FROM 'S'
    AND c.codveiculo IS NOT NULL
    AND c.kmini IS NOT NULL
),
gaps AS (
  SELECT
    numero,
    (kmini - prev_kmfim) AS km_vazio
  FROM viagens
  WHERE prev_kmfim IS NOT NULL
    AND kmini > prev_kmfim
)
UPDATE {s}.conhecimento c
SET kmvazio = g.km_vazio
FROM gaps g
WHERE c.numero = g.numero
""".strip()


def sql_atualizar_km_vazio_manifestos(schema: str) -> str:
    """Espelha conhecimento.kmvazio no MDF-e ligado ao mesmo CT-e (compatibilidade)."""
    s = _schema_sql(schema)
    return f"""
WITH manif_map AS (
  SELECT DISTINCT ON (c.numero)
    c.numero,
    c.kmvazio AS km_vazio,
    mc.codmanif
  FROM {s}.conhecimento c
  INNER JOIN {s}.manifconhecimento mc ON mc.numero = c.numero
  WHERE c.kmvazio IS NOT NULL
    AND c.kmvazio > 0
  ORDER BY c.numero, mc.codmanif DESC
)
UPDATE {s}.manif m
SET kmvazio = mm.km_vazio
FROM manif_map mm
WHERE m.codmanif = mm.codmanif
""".strip()


def sql_contar_km_vazio_preenchidos(schema: str) -> str:
    s = _schema_sql(schema)
    return f"""
SELECT
  COUNT(*) FILTER (WHERE kmvazio IS NOT NULL AND kmvazio > 0) AS ctes_com_km_vazio,
  COALESCE(SUM(kmvazio) FILTER (WHERE kmvazio > 0), 0) AS soma_km_vazio
FROM {s}.conhecimento;
"""


def aplicar_patch_km_vazio_restore(
    executar_sql,
    schema: str,
    apartamento_id: int | None = None,
    log=None,
) -> None:
    """executar_sql(sql) — mesma assinatura de sati_db_restore._executar_sql_autocommit."""
    schema_sql = _schema_sql(schema)
    executar_sql(sql_ensure_kmvazio_column(schema_sql, "conhecimento"))
    executar_sql(sql_ensure_kmvazio_column(schema_sql, "manif"))

    executar_sql(sql_disable_table_triggers(schema_sql, "conhecimento"))
    try:
        executar_sql(sql_atualizar_km_vazio_conhecimentos(schema_sql))
    finally:
        executar_sql(sql_enable_table_triggers(schema_sql, "conhecimento"))

    executar_sql(sql_disable_manif_triggers(schema_sql))
    try:
        executar_sql(sql_atualizar_km_vazio_manifestos(schema_sql))
    finally:
        executar_sql(sql_enable_manif_triggers(schema_sql))

    if log:
        log(
            apartamento_id,
            f"Km vazio entre viagens aplicado no schema {schema_sql} "
            "(conhecimento.kmvazio = kmini atual − kmfim da viagem anterior, por veículo).",
        )
