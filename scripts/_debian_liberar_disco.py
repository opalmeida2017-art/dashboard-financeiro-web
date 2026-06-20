"""Libera espaço no Debian e reenvia sati_db_restore."""
import paramiko
import time

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
LOCAL = r"c:\python\BIWEB"


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode(errors="replace")


def sudo(c, cmd, timeout=300):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    return o.read().decode(errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print("=== disco antes ===")
    print(run(c, "df -h / /tmp /var/tmp /home 2>/dev/null"))

    print("=== limpeza ===")
    cmds = [
        f"rm -rf /tmp/sati_restore_* /tmp/sati_extract /tmp/sati_t /var/tmp/sati_* 2>/dev/null",
        f"find {APP} -maxdepth 3 -name 'sati_restore_*' -type d -mtime +0 -exec rm -rf {{}} + 2>/dev/null",
        f"truncate -s 0 {APP}/rq_worker.log 2>/dev/null; truncate -s 0 {APP}/restore_manual.log 2>/dev/null",
        "journalctl --vacuum-size=80M 2>/dev/null || true",
        "apt-get clean 2>/dev/null || true",
    ]
    for cmd in cmds:
        print(run(c, cmd, timeout=60))

    print("=== disco depois ===")
    print(run(c, "df -h / /tmp /var/tmp /home 2>/dev/null"))

    sftp = c.open_sftp()
    sftp.put(f"{LOCAL}\\sati_db_restore.py", f"{APP}/sati_db_restore.py")
    sftp.close()

    print(
        run(
            c,
            f"mkdir -p /home/oitamar/tmp_sati && chmod 700 /home/oitamar/tmp_sati && "
            f"rm -rf /home/oitamar/tmp_sati/sati_restore_* 2>/dev/null; "
            f"(grep -q '^SATI_RESTORE_TMPDIR=' {APP}/.env && "
            f"sed -i 's|^SATI_RESTORE_TMPDIR=.*|SATI_RESTORE_TMPDIR=/home/oitamar/tmp_sati|' {APP}/.env || "
            f"echo 'SATI_RESTORE_TMPDIR=/home/oitamar/tmp_sati' >> {APP}/.env); "
            f"grep SATI_RESTORE_TMPDIR {APP}/.env",
            30,
        )
    )

    c.close()
    print("Limpeza concluída. Rode novamente: python scripts/_deploy_restore_fix_debian.py")


if __name__ == "__main__":
    main()
