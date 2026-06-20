"""Compara tenants rio-bonito vs wcarlos no Debian (sem imprimir senhas)."""
import re
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def run(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=60):
    i, o, _ = c.exec_command(f"sudo -S bash -lc {repr(cmd)}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


def parse_tenant_env(path: str) -> dict:
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "=" not in line or line.strip().startswith("#"):
                    continue
                k, v = line.strip().split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def slug_from_uri(uri: str) -> str | None:
    m = re.search(r"/(?:biweb|acesso)/([a-z0-9][a-z0-9_-]*)", uri or "", re.I)
    return m.group(1).lower() if m else None


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    print("=== painel_bi_tenant ===")
    print(
        run(
            c,
            "sudo -u postgres psql -d nfe_web -c "
            "\"SELECT slug, pg_database, ativo, left(url, 70) AS url FROM painel_bi_tenant ORDER BY slug\"",
            t=30,
        )
    )

    print("=== pastas em /opt/biweb/tenants ===")
    print(run(c, "ls -1 /opt/biweb/tenants/ 2>/dev/null"))

    # Ler tenant.env via SFTP (sem DATABASE_URL completo na saída)
    sftp = c.open_sftp()
    tenants_root = "/opt/biweb/tenants"
    try:
        dirs = sftp.listdir(tenants_root)
    except OSError:
        dirs = []
    print("\n=== tenant.env (slug, banco, schema) ===")
    env_map = {}
    for d in sorted(dirs):
        env_path = f"{tenants_root}/{d}/tenant.env"
        try:
            with sftp.file(env_path, "r") as f:
                raw = f.read().decode("utf-8", errors="replace")
        except OSError:
            continue
        env = {}
        for line in raw.splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            k, v = line.strip().split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
        slug = env.get("BI_TENANT_SLUG", d)
        db = env.get("BI_PG_DATABASE", "?")
        sch = env.get("SATI_SCHEMA", "?")
        env_map[slug.lower()] = {"pasta": d, "db": db, "schema": sch}
        print(f"  pasta={d} | slug={slug} | db={db} | schema={sch}")

    sftp.close()

    print("\n=== slug extraído das URLs ===")
    urls = [
        "https://dadosfrete.duckdns.org:8443/biweb/rio-bonito/",
        "https://dadosfrete.duckdns.org:8443/biweb/wcarlos/",
        "https://dadosfrete.duckdns.org:8443/biweb/w-carlos/",
    ]
    for u in urls:
        s = slug_from_uri(u)
        hit = env_map.get(s or "", {})
        print(f"  {u}")
        print(f"    -> slug URL: {s}")
        print(f"    -> tenant.env: {hit or 'NAO ENCONTRADO'}")

    print("\n=== nginx location biweb (8443) ===")
    print(run(c, "grep -n 'biweb\\|8443' /etc/nginx/sites-enabled/default 2>/dev/null | head -40"))
    print(run(c, "awk '/location.*biweb/,/^    }/' /etc/nginx/sites-enabled/default 2>/dev/null | head -40"))

    print("\n=== contagem conhecimento ===")
    for db, sch in (("bi_rio_bonito", "c3219"), ("bi_wcarlos", "c2910")):
        out = run(
            c,
            f"sudo -u postgres psql -d {db} -tAc "
            f"\"SELECT count(*) FROM {sch}.conhecimento\" 2>/dev/null || echo MISSING",
            t=30,
        )
        print(f"  {db}.{sch}: {out.strip()}")

    print("\n=== teste resolucao slug (curl interno) ===")
    for path in ("/biweb/rio-bonito/", "/biweb/wcarlos/"):
        out = run(
            c,
            f"curl -sS --max-time 10 -H 'X-Forwarded-Uri: {path}' "
            f"-H 'Cookie: ' http://127.0.0.1:8000/ 2>&1 | grep -o 'BIWEB[^<]*' | head -1",
            t=20,
        )
        print(f"  {path} -> titulo: {out.strip() or '(sem match)'}")

    c.close()


if __name__ == "__main__":
    main()
