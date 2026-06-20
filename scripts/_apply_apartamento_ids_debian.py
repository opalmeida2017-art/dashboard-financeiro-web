"""Aplica apartamento_id wcarlos=1, rio-bonito=2 no Debian (sem sudo no remoto)."""
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
NFE = "/opt/nfe-web"
LOCAL = Path(r"c:\python\BIWEB")

APARTAMENTOS = {
    "wcarlos": 1,
    "rio-bonito": 2,
}


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", "replace")


def sudo(c, cmd, t=120):
    i, o, _ = c.exec_command(f"sudo -S bash -lc {repr(cmd)}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", "replace")


def patch_env_remote(c, tenant_dir: str, apt_id: int):
    for nome in ("tenant.env", ".env"):
        cmd = (
            f"test -f {tenant_dir}/{nome} || test {nome} = tenant.env || exit 0; "
            f"grep -v '^BIWEB_TRANSPORTADORA_ID=' {tenant_dir}/{nome} 2>/dev/null "
            f"> /tmp/_env_{nome} || true; "
            f"echo BIWEB_TRANSPORTADORA_ID={apt_id} >> /tmp/_env_{nome}; "
            f"cp /tmp/_env_{nome} {tenant_dir}/{nome}; "
            f"chown nfe-web:nfe-web {tenant_dir}/{nome}"
        )
        print(sudo(c, cmd))


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    # Patch bi_store / registry se ainda não aplicado
    bi_store = f"{NFE}/bi_store.py"
    reg = f"{NFE}/bi_tenant_registry.py"
    sftp = c.open_sftp()
    tmp_bs = LOCAL / "scripts" / "_tmp_bi_store.py"
    tmp_reg = LOCAL / "scripts" / "_tmp_bi_tenant_registry.py"
    try:
        sftp.get(bi_store, str(tmp_bs))
        sftp.get(reg, str(tmp_reg))
        for path, old, new in (
            (tmp_bs, "(slug, razao, pg_db, None, url)", "(slug, razao, pg_db, apartamento_id, url)"),
            (
                tmp_reg,
                "item = _store().register_tenant(razao, slug, url, None, pg_db)",
                "item = _store().register_tenant(razao, slug, url, apartamento_id, pg_db)",
            ),
            (tmp_reg, '"apartamento_id": None,', '"apartamento_id": apartamento_id,'),
        ):
            text = path.read_text(encoding="utf-8")
            if old in text:
                path.write_text(text.replace(old, new, 1), encoding="utf-8")
        sftp.put(str(tmp_bs), bi_store)
        sftp.put(str(tmp_reg), reg)
    except OSError:
        pass

    sftp.put(
        str(LOCAL / "scripts" / "_server_provision_bi_tenant.py"),
        f"{NFE}/deploy/provision_bi_tenant.py",
    )
    sftp.put(
        str(LOCAL / "scripts" / "_server_painel.js"),
        f"{NFE}/frontend/painel/painel.js",
    )
    sftp.close()

    for slug, apt_id in APARTAMENTOS.items():
        tenant_dir = f"/opt/biweb/tenants/{slug}"
        print(f"\n=== {slug} -> apartamento {apt_id} ===")
        print(
            sudo(
                c,
                f"-u postgres psql -d nfe_web -c "
                f"\"UPDATE painel_bi_tenant SET apartamento_id={apt_id}, updated_at=NOW() "
                f"WHERE LOWER(slug)='{slug}';\"",
            )
        )
        patch_env_remote(c, tenant_dir, apt_id)
        print(
            run(
                c,
                f"grep BIWEB_TRANSPORTADORA_ID {tenant_dir}/tenant.env 2>/dev/null || echo 'sem env'",
            )
        )
        pg_db = f"bi_{slug.replace('-', '_')}"
        migrar = (
            f"cd {NFE} && ./venv/bin/python -c \""
            f"import sys; sys.path.insert(0,'{NFE}'); "
            f"import psycopg2, database_connection as dc; "
            f"from deploy.provision_bi_tenant import _migrar_apartamento_id_cur; "
            f"conn=psycopg2.connect(**{{**dc._dsn(),'dbname':'{pg_db}'}}); "
            f"conn.autocommit=False; cur=conn.cursor(); "
            f"cur.execute('SELECT id FROM apartamentos ORDER BY id LIMIT 1'); "
            f"row=cur.fetchone(); "
            f"(row and int(row[0])!={apt_id}) and _migrar_apartamento_id_cur(cur,int(row[0]),{apt_id}); "
            f"conn.commit(); conn.close(); print('banco {pg_db} ok apt {apt_id}')\""
        )
        print(run(c, migrar, t=60))
        if apt_id != 1:
            print(
                sudo(
                    c,
                    f"test -d {tenant_dir}/downloads/1 && "
                    f"mv {tenant_dir}/downloads/1 {tenant_dir}/downloads/{apt_id} || true; "
                    f"mkdir -p {tenant_dir}/downloads/{apt_id}; "
                    f"chown -R nfe-web:nfe-web {tenant_dir}/downloads",
                )
            )

    print("\n=== painel_bi_tenant ===")
    print(
        sudo(
            c,
            "-u postgres psql -d nfe_web -c "
            "\"SELECT slug, apartamento_id, pg_database FROM painel_bi_tenant ORDER BY apartamento_id, slug\"",
        )
    )
    print(run(c, "pkill -HUP -f 'gunicorn.*127.0.0.1:8000' 2>/dev/null || true"))
    c.close()


if __name__ == "__main__":
    main()
