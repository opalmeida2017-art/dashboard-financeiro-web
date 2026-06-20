"""Busca colunas *embarc* na tabela conhecimento (SATI / PostgreSQL)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from sqlalchemy import create_engine, text

url = os.getenv("SATI_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()
if not url:
    raise SystemExit("SATI_DATABASE_URL / DATABASE_URL não definido no .env")
engine = create_engine(url)

schema = os.getenv("SATI_SCHEMA", "c3332")

sql_match = """
SELECT ordinal_position, column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_schema = :schema AND table_name = 'conhecimento'
  AND column_name ILIKE '%embarc%'
ORDER BY ordinal_position
"""

sql_total = """
SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema = :schema AND table_name = 'conhecimento'
"""

sql_like_embarcado = """
SELECT ordinal_position, column_name
FROM information_schema.columns
WHERE table_schema = :schema AND table_name = 'conhecimento'
  AND column_name ILIKE '%embarcado%'
ORDER BY ordinal_position
"""

sql_extra = """
SELECT ordinal_position, column_name
FROM information_schema.columns
WHERE table_schema = :schema AND table_name = 'conhecimento'
  AND (column_name ILIKE '%embarque%' OR column_name ILIKE '%carreg%')
ORDER BY ordinal_position
"""

sql_embarcador_tbl = """
SELECT column_name FROM information_schema.columns
WHERE table_schema = :schema AND table_name = 'embarcador'
ORDER BY ordinal_position
"""

with engine.connect() as conn:
    total = conn.execute(text(sql_total), {"schema": schema}).scalar()
    rows = conn.execute(text(sql_match), {"schema": schema}).fetchall()
    exato = conn.execute(text(sql_like_embarcado), {"schema": schema}).fetchall()
    extra = conn.execute(text(sql_extra), {"schema": schema}).fetchall()
    emb_tbl = conn.execute(text(sql_embarcador_tbl), {"schema": schema}).fetchall()

print(f"schema: {schema}")
print(f"total colunas conhecimento: {total}")
print("\n--- colunas com 'embarc' no nome ---")
for pos, col, dtype, udt in rows:
    print(f"  {pos:3} {col:35} {dtype or udt}")

print("\n--- colunas com 'embarcado' no nome ---")
if exato:
    for pos, col in exato:
        print(f"  {pos:3} {col}")
else:
    print("  (nenhuma coluna com nome exato 'embarcado')")

print("\n--- colunas embarque / carregamento ---")
for pos, col in extra:
    print(f"  {pos:3} {col}")

print("\n--- tabela embarcador (colunas) ---")
if emb_tbl:
    print("  ", ", ".join(r[0] for r in emb_tbl))
else:
    print("  (tabela embarcador não encontrada no schema)")
