"""Valida vínculo CT-e <-> nomearq (COMPROVANT_NNNN)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from sqlalchemy import text
from sati_integration.db.sati_source import get_sati_engine

schema = __import__("os").getenv("SATI_SCHEMA", "c3332")

# Padrões do SATI (Painel de Documentos)
RE_COMPROVANT = re.compile(
    r"(?:^|/)(?:\d{4}/)?(?:COMPROVANTEDEDESCARGA/)?"
    r"(?:DESCARGA/)?2COMPROVANT_(\d+)\.(pdf|jpeg|jpg|png)$",
    re.IGNORECASE,
)


def extrair_numero_cte(nomearq: str) -> int | None:
    if not nomearq:
        return None
    path = nomearq.replace("\\", "/").strip()
    m = RE_COMPROVANT.search(path)
    if m:
        return int(m.group(1))
    m2 = re.search(r"2COMPROVANT_(\d+)", path, re.I)
    return int(m2.group(1)) if m2 else None


def main():
    engine = get_sati_engine()
    alvo = 7965

    with engine.connect() as conn:
        print("=== CT-e 7965 no conhecimento ===")
        for r in conn.execute(
            text(
                f"""
                SELECT numero, numeroconhecimento, cancelado,
                       chegoucomprovante::text
                FROM {schema}.conhecimento
                WHERE numero = :n OR numeroconhecimento = :n
                LIMIT 5
                """
            ),
            {"n": alvo},
        ):
            print(r)

        print("\n=== documento para chavetabela 7965 ===")
        for r in conn.execute(
            text(
                f"""
                SELECT coddocumento, chavetabela, nomearq::text, codtipodoc::text
                FROM {schema}.documento
                WHERE nometabela = 'CONHECIMENTO' AND chavetabela = :n
                """
            ),
            {"n": alvo},
        ):
            print(r)
            arq = r[2]
            ext = extrair_numero_cte(arq)
            print(f"  -> extraído do nomearq: {ext} | bate chavetabela: {ext == alvo}")

        print("\n=== Validação em lote (amostra 500) ===")
        rows = conn.execute(
            text(
                f"""
                SELECT chavetabela, nomearq::text
                FROM {schema}.documento
                WHERE nometabela = 'CONHECIMENTO'
                  AND nomearq::text ILIKE '%COMPROVANT%'
                ORDER BY coddocumento DESC
                LIMIT 500
                """
            )
        ).fetchall()

    ok = mismatch = sem_parse = 0
    for chave, arq in rows:
        num = extrair_numero_cte(arq)
        if num is None:
            sem_parse += 1
        elif num == int(chave):
            ok += 1
        else:
            mismatch += 1
            if mismatch <= 5:
                print(f"DIVERGE chave={chave} arquivo={num} | {arq}")

    print(f"OK={ok} diverge={mismatch} sem_parse={sem_parse} total={len(rows)}")

    link = "2026/COMPROVANTEDEDESCARGA/2COMPROVANT_7965.pdf"
    print(f"\nLink usuário -> numero interno CT-e: {extrair_numero_cte(link)}")

    with engine.connect() as conn:
        print("\n=== Busca por nomearq contendo 7965 ===")
        for r in conn.execute(
            text(
                f"""
                SELECT d.chavetabela, LEFT(d.nomearq::text, 90), c.numero, c.numeroconhecimento
                FROM {schema}.documento d
                LEFT JOIN {schema}.conhecimento c ON c.numero = d.chavetabela
                WHERE d.nometabela = 'CONHECIMENTO'
                  AND d.nomearq::text ILIKE '%7965%'
                LIMIT 5
                """
            )
        ):
            print(r)
        print("\n=== Exemplo 6918 (da tela) ===")
        for r in conn.execute(
            text(
                f"""
                SELECT d.chavetabela, LEFT(d.nomearq::text, 80),
                       c.numero, c.numeroconhecimento
                FROM {schema}.documento d
                JOIN {schema}.conhecimento c ON c.numero = d.chavetabela
                WHERE d.nomearq::text ILIKE '%2COMPROVANT_6918%'
                LIMIT 2
                """
            )
        ):
            print(r)

        print("\n=== codtipodoc 69 (Painel SATI) ===")
        for r in conn.execute(
            text(
                f"""
                SELECT codtipodoc::text, COUNT(*)
                FROM {schema}.documento
                WHERE nometabela = 'CONHECIMENTO' AND nomearq ILIKE '%COMPROVANT%'
                GROUP BY 1 ORDER BY 2 DESC LIMIT 5
                """
            )
        ):
            print(r)


if __name__ == "__main__":
    main()
