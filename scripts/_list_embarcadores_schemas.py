"""Lista embarcadores no SATI local e no Debian (rio-bonito)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from sqlalchemy import create_engine, text

url = os.getenv("SATI_DATABASE_URL", "").strip()
if not url:
    raise SystemExit("SATI_DATABASE_URL não definido")

schemas = []
for s in (os.getenv("SATI_SCHEMA", ""), "c2910", "c3332", "rio_bonito"):
    s = (s or "").strip()
    if s and s not in schemas:
        schemas.append(s)

engine = create_engine(url)

sql_tbl = """
SELECT codembarcador, nome FROM {schema}.embarcador
WHERE codembarcador IS NOT NULL AND codembarcador > 0
ORDER BY nome
"""

sql_conh = """
SELECT DISTINCT c.codembarcador, emb.nome
FROM {schema}.conhecimento c
LEFT JOIN {schema}.embarcador emb ON emb.codembarcador = c.codembarcador
WHERE c.codembarcador IS NOT NULL AND c.codembarcador > 0
  AND c.cancelado IS DISTINCT FROM 'S'
ORDER BY 1
"""

for schema in schemas:
    try:
        with engine.connect() as conn:
            n_tbl = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema=:s AND table_name='embarcador'"
                ),
                {"s": schema},
            ).scalar()
            if not n_tbl:
                print(f"\n[{schema}] tabela embarcador ausente")
                continue
            tbl = conn.execute(text(sql_tbl.format(schema=schema))).fetchall()
            conh = conn.execute(text(sql_conh.format(schema=schema))).fetchall()
        print(f"\n=== {schema} ===")
        print(f"cadastro embarcador: {len(tbl)}")
        for r in tbl[:15]:
            print(f"  {r[0]} - {r[1]}")
        if len(tbl) > 15:
            print(f"  ... +{len(tbl)-15}")
        print(f"distintos em conhecimento: {len(conh)}")
        for r in conh[:10]:
            print(f"  {r[0]} - {r[1]}")
    except Exception as e:
        print(f"\n[{schema}] erro: {e}")
