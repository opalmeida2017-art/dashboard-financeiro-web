"""Diagnóstico: domínios e tabelas faltando em bi_wcarlos após restore."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
DB = "bi_wcarlos"
SCHEMA = "c2910"
OBRIG = (
    "conhecimento", "veiculo", "nota", "itemnota", "filial",
    "cliente", "motorista",
)


def run(c, cmd, t=45):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode("utf-8", "replace")


def psql(c, sql):
    esc = sql.replace('"', '\\"')
    return run(
        c,
        f'sudo -u postgres psql -d {DB} -c "{esc}"',
    )


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    print(f"=== Banco {DB} existe? ===")
    print(run(c, f"sudo -u postgres psql -tAc \"SELECT 1 FROM pg_database WHERE datname='{DB}'\""))

    print(f"\n=== Tabelas obrigatórias em {SCHEMA} ===")
    for tbl in OBRIG:
        ok = run(
            c,
            f"sudo -u postgres psql -d {DB} -tAc "
            f"\"SELECT to_regclass('{SCHEMA}.{tbl}')\"",
        ).strip()
        status = "OK" if ok and ok != "" else "FALTA"
        print(f"  {SCHEMA}.{tbl}: {status}")

    print(f"\n=== Total tabelas {SCHEMA} ===")
    print(
        run(
            c,
            f"sudo -u postgres psql -d {DB} -tAc "
            f"\"SELECT count(*) FROM pg_tables WHERE schemaname='{SCHEMA}'\"",
        ).strip()
    )

    print("\n=== Domínios c2910 vs public.dom_* ===")
    print(
        run(
            c,
            f"sudo -u postgres psql -d {DB} -c "
            "\"SELECT "
            "(SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
            "WHERE n.nspname='c2910' AND t.typtype='d') AS dom_c2910, "
            "(SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
            "WHERE n.nspname='public' AND t.typtype='d' AND t.typname LIKE 'dom_%') AS dom_public\"",
        )
    )

    print("\n=== Domínios em c2910 SEM espelho em public ===")
    print(
        run(
            c,
            f"sudo -u postgres psql -d {DB} -c "
            "\"SELECT c.typname "
            "FROM pg_type c "
            "JOIN pg_namespace nc ON nc.oid = c.typnamespace "
            "WHERE nc.nspname = 'c2910' AND c.typtype = 'd' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM pg_type p "
            "  JOIN pg_namespace np ON np.oid = p.typnamespace "
            "  WHERE np.nspname = 'public' AND p.typname = c.typname AND p.typtype = 'd'"
            ") "
            "ORDER BY 1 LIMIT 30\"",
        )
    )
    print(
        run(
            c,
            f"sudo -u postgres psql -d {DB} -tAc "
            "\"SELECT count(*) FROM pg_type c "
            "JOIN pg_namespace nc ON nc.oid = c.typnamespace "
            "WHERE nc.nspname = 'c2910' AND c.typtype = 'd' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM pg_type p "
            "  JOIN pg_namespace np ON np.oid = p.typnamespace "
            "  WHERE np.nspname = 'public' AND p.typname = c.typname AND p.typtype = 'd'"
            ")\"",
        ).strip()
        + " domínios c2910 sem espelho em public (total)"
    )

    print("\n=== Amostra tabelas FALTANDO (dump SATI costuma ter ~490) ===")
    print(
        run(
            c,
            f"sudo -u postgres psql -d {DB} -c "
            "\"SELECT tablename FROM (VALUES "
            "('cliente'),('conhecimento'),('veiculo'),('nota'),('itemnota'),"
            "('filial'),('motorista'),('cidade'),('fornecedor'),('mercadoria'),"
            "('embarcador'),('usuarios'),('parametros')) AS t(tablename) "
            "WHERE to_regclass('c2910.' || tablename) IS NULL "
            "ORDER BY 1\"",
        )
    )

    print("\n=== Colunas da tabela cliente no DUMP (pg_restore -l) ===")
    print(
        run(
            c,
            "test -f /home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910.dump && "
            "pg_restore -l /home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910.dump 2>/dev/null | "
            "grep -i 'TABLE DATA c2910 cliente\\|TABLE c2910 cliente' | head -5 || "
            "echo 'dump não encontrado'",
        )
    )

    print("\n=== Erro típico: domínios usados por cliente (se existisse definição no dump) ===")
    print(
        run(
            c,
            "test -f /home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910.dump && "
            "/usr/lib/postgresql/17/bin/pg_restore -f - /home/oitamar/dashboard-financeiro-web/downloads/1/SATI-c2910.dump 2>/dev/null | "
            "grep -A2 'CREATE TABLE c2910.cliente' | head -20 || echo sem dump",
            t=120,
        )
    )

    c.close()


if __name__ == "__main__":
    main()
