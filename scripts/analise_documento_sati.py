"""Uso: python analise_documento_sati.py (no servidor ou local com .env SATI)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from sqlalchemy import text
from sati_integration.db.sati_source import get_sati_engine

engine = get_sati_engine()
schema = os.getenv("SATI_SCHEMA", "c3332")


def run(label, sql):
    print(f"\n=== {label} ===")
    try:
        with engine.connect() as conn:
            for row in conn.execute(text(sql)).fetchall():
                print(row)
    except Exception as exc:
        print("ERRO:", exc)


def main():
    run(
        "tabelas doc/comprov",
        f"""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = '{schema}'
          AND (table_name ILIKE '%document%' OR table_name ILIKE '%comprov%'
               OR table_name ILIKE '%anexo%' OR table_name ILIKE '%arquivo%'
               OR table_name ILIKE '%imagem%')
        ORDER BY 1
        """,
    )
    run(
        "colunas documento",
        f"""
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = '{schema}' AND table_name = 'documento'
        ORDER BY ordinal_position
        """,
    )
    run("total registros", f"SELECT COUNT(*) FROM {schema}.documento")
    run(
        "por nometabela",
        f"""
        SELECT nometabela, COUNT(*) FROM {schema}.documento
        GROUP BY nometabela ORDER BY 2 DESC LIMIT 12
        """,
    )
    run(
        "CT-e com nomearq",
        f"""
        SELECT COUNT(*) FROM {schema}.documento
        WHERE nometabela = 'CONHECIMENTO'
          AND NULLIF(TRIM(nomearq::text), '') IS NOT NULL
        """,
    )
    run(
        "amostra CT-e",
        f"""
        SELECT coddocumento, chavetabela,
               LEFT(nomearq::text, 80) AS nomearq
        FROM {schema}.documento
        WHERE nometabela = 'CONHECIMENTO'
          AND NULLIF(TRIM(nomearq::text), '') IS NOT NULL
        ORDER BY coddocumento DESC LIMIT 10
        """,
    )
    # colunas que podem guardar conteúdo ou caminho
    run(
        "colunas texto/binario",
        f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = '{schema}' AND table_name = 'documento'
          AND (data_type IN ('bytea', 'text') OR column_name ILIKE '%caminho%'
               OR column_name ILIKE '%arq%' OR column_name ILIKE '%path%'
               OR column_name ILIKE '%img%' OR column_name ILIKE '%blob%')
        ORDER BY 1
        """,
    )
    run(
        "codtipodoc comprovante",
        f"""
        SELECT d.codtipodoc::text, td.descricao::text, COUNT(*)
        FROM {schema}.documento d
        LEFT JOIN {schema}.tipodocumento td ON td.codtipodoc = d.codtipodoc
        WHERE d.nometabela = 'CONHECIMENTO'
          AND d.nomearq::text ILIKE '%COMPROVANT%'
        GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10
        """,
    )
    run(
        "extensoes CT-e",
        f"""
        SELECT
          CASE WHEN nomearq::text ILIKE '%.pdf' THEN 'pdf'
               WHEN nomearq::text ILIKE '%.jpg' OR nomearq::text ILIKE '%.jpeg' THEN 'jpg'
               WHEN nomearq::text ILIKE '%.png' THEN 'png'
               ELSE 'outro' END AS tipo,
          COUNT(*)
        FROM {schema}.documento
        WHERE nometabela = 'CONHECIMENTO'
          AND NULLIF(TRIM(nomearq::text), '') IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
        """,
    )
    run(
        "chegoucomprovante conhecimento",
        f"""
        SELECT chegoucomprovante::text, COUNT(*)
        FROM {schema}.conhecimento
        WHERE cancelado IS DISTINCT FROM 'S'
        GROUP BY 1 ORDER BY 2 DESC
        """,
    )


if __name__ == "__main__":
    main()
