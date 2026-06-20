"""Lista colunas da tabela SATI item e verifica investimento."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from sqlalchemy import text
from sati_integration.db.sati_source import get_sati_engine

schema = os.getenv("SATI_SCHEMA", "c3332")
engine = get_sati_engine()

sql_cols = f"""
SELECT ordinal_position, column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_schema = '{schema}' AND table_name = 'item'
ORDER BY ordinal_position
"""

sql_inv = f"""
SELECT column_name FROM information_schema.columns
WHERE table_schema = '{schema}' AND table_name = 'item'
  AND column_name ILIKE '%invest%'
"""

with engine.connect() as conn:
    rows = conn.execute(text(sql_cols)).fetchall()
    inv = conn.execute(text(sql_inv)).fetchall()
    try:
        cnt = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.item")).scalar()
    except Exception as e:
        cnt = f"erro: {e}"

print(f"schema: {schema}")
print(f"total colunas item: {len(rows)}")
print(f"registros item: {cnt}")
print("\n--- colunas com 'invest' no nome ---")
for r in inv:
    print(r[0])
if not inv:
    print("(nenhuma)")

print("\n--- todas as colunas item ---")
for pos, col, dtype, udt in rows:
    print(f"{pos:3} {col:40} {dtype or udt}")
