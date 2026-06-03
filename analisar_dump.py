import re
from pathlib import Path

DUMP_PATH = Path(__file__).parent / "SATI-c3332.dump"
OUT_PATH = Path(__file__).parent / "SATI-c3332_analise.txt"


def main():
    data = DUMP_PATH.read_bytes()
    text = data.decode("latin-1", errors="replace")

    create_pattern = re.compile(
        r"CREATE TABLE (c3332\.[^\s(]+)\s*\((.*?)\);",
        re.S | re.I,
    )
    tables = {}
    for match in create_pattern.finditer(text):
        name = match.group(1)
        cols_block = match.group(2)
        cols = []
        for line in cols_block.split("\n"):
            line = line.strip().rstrip(",")
            if not line:
                continue
            upper = line.upper()
            if upper.startswith(
                ("CONSTRAINT", "PRIMARY KEY", "UNIQUE", "FOREIGN KEY", "CHECK")
            ):
                continue
            col_match = re.match(r'"([^"]+)"|([a-zA-Z_][a-zA-Z0-9_]*)', line)
            if not col_match:
                continue
            col = col_match.group(1) or col_match.group(2)
            rest = line[col_match.end() :].strip()
            cols.append({"name": col, "definition": rest})
        tables[name] = cols

    copy_tables = sorted(set(re.findall(r"COPY (c3332\.[^\s(]+)", text, re.I)))
    copy_lookup = {name.lower() for name in copy_tables}

    lines = [
        "ANALISE DO DUMP: SATI-c3332.dump",
        "=" * 60,
        f"Tamanho: {len(data) / 1024 / 1024:.1f} MB",
        "Formato: PostgreSQL custom dump (PGDMP v1.16 / PostgreSQL 16)",
        "Schema: c3332",
        f"Total de tabelas: {len(tables)}",
        f"Tabelas com dados (COPY): {len(copy_tables)}",
        "",
        "LISTA DE TABELAS:",
        "-" * 60,
    ]

    for index, tname in enumerate(sorted(tables.keys()), 1):
        has_data = tname.lower() in copy_lookup
        lines.append(
            f"{index:4}. {tname} | {len(tables[tname])} colunas | dados: {'Sim' if has_data else 'Nao'}"
        )

    lines.extend(["", "DETALHES DAS TABELAS:", "=" * 60])

    for tname in sorted(tables.keys()):
        cols = tables[tname]
        has_data = tname.lower() in copy_lookup
        lines.append("")
        lines.append(f"--- {tname} ---")
        lines.append(f"Colunas: {len(cols)} | Tem dados: {'Sim' if has_data else 'Nao'}")
        for col in cols:
            lines.append(f"  - {col['name']}: {col['definition']}")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Schema: c3332")
    print(f"Total de tabelas: {len(tables)}")
    print(f"Tabelas com dados: {len(copy_tables)}")
    print(f"Relatorio completo: {OUT_PATH}")
    print()
    print("Primeiras 40 tabelas:")
    for index, tname in enumerate(sorted(tables.keys())[:40], 1):
        has_data = tname.lower() in copy_lookup
        print(
            f"{index:3}. {tname} ({len(tables[tname])} cols, dados={'Sim' if has_data else 'Nao'})"
        )


if __name__ == "__main__":
    main()
