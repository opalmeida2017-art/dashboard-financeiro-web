"""Deploy correção restore SATI + variáveis .env no Debian."""
import re
from pathlib import Path

import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
LOCAL = Path(__file__).resolve().parents[1]
ENV = f"{APP}/.env"

ARQUIVOS = [
    "robos/coletor_atualizacao_bd.py",
    "sati_db_restore.py",
]


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    o.channel.settimeout(timeout)
    try:
        out = (o.read() + e.read()).decode(errors="replace")
    except Exception:
        out = ""
    return out


def run_bg(c, cmd):
    """Comando em background — não espera saída longa."""
    c.exec_command(cmd)


def sudo(c, cmd, timeout=120):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    return o.read().decode(errors="replace")


def upsert(text: str, key: str, val: str) -> str:
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={val}"
    return pat.sub(line, text) if pat.search(text) else text.rstrip() + "\n" + line + "\n"


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    sftp = c.open_sftp()
    for rel in ARQUIVOS:
        print(f"Upload: {rel}")
        sftp.put(str(LOCAL / rel), f"{APP}/{rel}")

    tmp_env = LOCAL / "scripts" / "_env_restore_fix.tmp"
    sftp.get(ENV, str(tmp_env))
    text = tmp_env.read_text(encoding="utf-8")
    text = upsert(text, "SATI_PG_RESTORE", "/usr/lib/postgresql/17/bin/pg_restore")
    text = upsert(text, "SATI_SCHEMA", "c2910")
    text = upsert(text, "SATI_RESTORE_USE_SUDO_POSTGRES", "1")
    text = upsert(text, "SATI_RESTORE_FILE_OWNER", "postgres:postgres")
    text = upsert(text, "SATI_RESTORE_TMPDIR", "/home/oitamar/tmp_sati")
    tmp_env.write_text(text, encoding="utf-8", newline="\n")
    sftp.put(str(tmp_env), "/home/oitamar/.env.restore.new")
    sftp.close()
    tmp_env.unlink(missing_ok=True)

    print("=== atualizar .env ===")
    print(sudo(c, f"mv /home/oitamar/.env.restore.new {ENV} && chmod 600 {ENV}"))
    print(run(c, f"grep -E 'SATI_PG_RESTORE|SATI_RESTORE_|SATI_SCHEMA=' {ENV} | sed 's/=.*/=***/'"))

    print("=== testar sudo postgres ===")
    print(sudo(c, '-u postgres psql -d sat1_sati_is -tAc "SELECT 1"'))

    print("=== sudoers NOPASSWD restore ===")
    sudoers = (
        'oitamar ALL=(postgres) NOPASSWD: /usr/bin/psql, '
        '/usr/lib/postgresql/17/bin/pg_restore, /usr/lib/postgresql/16/bin/pg_restore'
    )
    print(
        sudo(
            c,
            f"bash -c 'echo \"{sudoers}\" > /etc/sudoers.d/biweb-sati-restore && "
            f"chmod 440 /etc/sudoers.d/biweb-sati-restore && visudo -c'",
        )
    )
    print(run(c, "sudo -n -u postgres psql -d sat1_sati_is -tAc 'SELECT 1'", 15))

    print("=== reiniciar RQ worker ===")
    run_bg(
        c,
        f"cd {APP} && pkill -f 'rq worker default' || true; sleep 2; "
        f"nohup ./venv/bin/rq worker default -u redis://localhost:6379 >> rq_worker.log 2>&1 &",
    )
    import time

    time.sleep(2)
    print(run(c, "pgrep -af 'rq worker' || echo '(sem worker)'", timeout=15))

    print("=== reiniciar gunicorn ===")
    run_bg(
        c,
        f"cd {APP} && pkill -f 'gunicorn.*127.0.0.1:8000.*app:app' || true; sleep 2; "
        f"./venv/bin/gunicorn --workers 3 --worker-class gevent --bind 127.0.0.1:8000 "
        f"--timeout 120 --log-level info --daemon --pid /tmp/gunicorn-dashboard.pid app:app",
    )
    time.sleep(3)
    print(run(c, "pgrep -af 'gunicorn.*8000' || echo '(sem gunicorn)'", timeout=15))

    print("=== limpar locks restore ===")
    print(run(c, f"rm -f {APP}/data/sati_restore.lock {APP}/downloads/1/painel_documentos_robo.lock"))
    print(
        run(
            c,
            "pkill -f 'processar_arquivo_zip_sati' || true; "
            "pkill -f 'sati_db_restore' || true; "
            "pkill -f 'restore_manual' || true",
            15,
        )
    )
    print(run(c, f"truncate -s 0 {APP}/restore_manual.log 2>/dev/null", 10))
    print(run(c, "rm -f /var/tmp/sati_* 2>/dev/null", 10))
    print("(Restore automático desativado — use scripts/_run_restore_once_debian.py)")

    c.close()
    print("Deploy restore concluído.")


if __name__ == "__main__":
    main()
