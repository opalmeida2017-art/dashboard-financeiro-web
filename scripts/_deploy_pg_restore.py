import re
from pathlib import Path

import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
ENV = f"{APP}/.env"
PG_RESTORE = "/usr/lib/postgresql/17/bin/pg_restore"


def sudo(c, cmd):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    return o.read().decode(errors="replace")


def upsert(text, key, val):
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={val}"
    return pat.sub(line, text) if pat.search(text) else text.rstrip() + "\n" + line + "\n"


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    sftp = c.open_sftp()
    sftp.put(
        str(Path(__file__).resolve().parents[1] / "sati_db_restore.py"),
        f"{APP}/sati_db_restore.py",
    )
    local_env = Path(__file__).parent / "_env_tmp"
    sftp.get(ENV, str(local_env))
    text = upsert(local_env.read_text(encoding="utf-8"), "SATI_PG_RESTORE", PG_RESTORE)
    local_env.write_text(text, encoding="utf-8", newline="\n")
    sftp.put(str(local_env), "/home/oitamar/.env.new")
    sftp.close()
    sudo(c, f"mv /home/oitamar/.env.new {ENV} && chmod 600 {ENV}")

    sudo(
        c,
        f"pkill -f 'gunicorn.*app:app' || true; sleep 2; "
        f"cd {APP} && ./venv/bin/gunicorn --workers 3 --worker-class gevent "
        f"--bind 127.0.0.1:8000 --daemon app:app",
    )

    _, o, _ = c.exec_command(
        f"find {APP}/downloads -name 'SATI*.zip' -printf '%T@ %p\\n' 2>/dev/null | sort -rn | head -1",
        timeout=15,
    )
    zip_line = o.read().decode().strip()
    print("zip:", zip_line or "(nenhum)")

    if zip_line:
        zip_path = zip_line.split(" ", 1)[-1]
        print("Restaurando dump já baixado (pode levar vários minutos)...")
        cmd = (
            f"cd {APP} && export $(grep -v '^#' {ENV} | xargs) && "
            f"./venv/bin/python -c \""
            f"from pathlib import Path; from sati_integration.robos from sati_integration.robos import sati_db_restore as s; "
            f"s.processar_arquivo_zip_sati(Path('{zip_path}'), apartamento_id=1)"
            f"\" 2>&1 | tail -30"
        )
        _, o, e = c.exec_command(cmd, timeout=7200)
        print(o.read().decode(errors="replace")[-3000:])
        err = e.read().decode(errors="replace")
        if err:
            print("stderr:", err[-1000:])

    _, o, _ = c.exec_command(f"grep SATI_PG_RESTORE {ENV}", timeout=5)
    print("env:", o.read().decode())
    c.close()
    local_env.unlink(missing_ok=True)
    print("Feito.")


if __name__ == "__main__":
    main()
