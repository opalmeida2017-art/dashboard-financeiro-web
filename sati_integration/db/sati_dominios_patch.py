"""Domínios SATI referenciados em tabelas mas ausentes em alguns dumps (ex. c2910).

Padrão validado no dump SATI-c3219-atual (Rio Bonito):
  CREATE DOMAIN c3219.dom_endereco255 AS character varying(255);
"""

from __future__ import annotations

import re

# nome -> tipo base PostgreSQL
DOMINIOS_ORFAOS: dict[str, str] = {
    "dom_endereco255": "character varying(255)",
}


def _schema_sql(schema: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "", (schema or "").strip()) or "c3332"


def sql_patch_dominios_orfaos(schema: str) -> str:
    """SQL que cria domínios ausentes no schema SATI e espelha em public."""
    schema_sql = _schema_sql(schema)
    parts: list[str] = [
        "DO $$",
        "BEGIN",
    ]
    for name, base in DOMINIOS_ORFAOS.items():
        n = re.sub(r"[^a-zA-Z0-9_]", "", name)
        parts.append(
            f"""
  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace ns ON ns.oid = t.typnamespace
    WHERE ns.nspname = '{schema_sql}' AND t.typname = '{n}' AND t.typtype = 'd'
  ) THEN
    EXECUTE format('CREATE DOMAIN %I.%I AS {base}', '{schema_sql}', '{n}');
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace ns ON ns.oid = t.typnamespace
    WHERE ns.nspname = 'public' AND t.typname = '{n}' AND t.typtype = 'd'
  ) THEN
    BEGIN
      EXECUTE format('CREATE DOMAIN public.%I AS {schema_sql}.%I', '{n}', '{n}');
    EXCEPTION WHEN undefined_object THEN
      EXECUTE format('CREATE DOMAIN public.%I AS {base}', '{n}');
    END;
  END IF;"""
        )
    parts.append("END $$;")
    return "\n".join(parts)


def aplicar_patch_cursor(cursor, schema: str) -> list[str]:
    """Aplica patch via cursor psycopg2. Retorna domínios que foram verificados."""
    cursor.execute(sql_patch_dominios_orfaos(schema))
    return list(DOMINIOS_ORFAOS.keys())


def aplicar_patch_restore(
    executar_sql,
    schema: str,
    apartamento_id: int | None = None,
    log=None,
) -> list[str]:
    """executar_sql(sql) — mesma assinatura de sati_db_restore._executar_sql_autocommit."""
    schema_sql = _schema_sql(schema)
    executar_sql(sql_patch_dominios_orfaos(schema_sql))
    if log:
        nomes = ", ".join(DOMINIOS_ORFAOS.keys())
        log(apartamento_id, f"Patch domínios SATI aplicado ({schema_sql}): {nomes}.")
    return list(DOMINIOS_ORFAOS.keys())
