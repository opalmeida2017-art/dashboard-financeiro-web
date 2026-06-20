"""Libera espaço em /var e reinicia PostgreSQL no Debian."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=300):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print("=== antes ===")
    print(run(c, "df -h /var /var/tmp /tmp"))

    cmds = [
        "du -sh /var/* 2>/dev/null | sort -hr | head -15",
        "rm -f /var/tmp/sati_* /var/tmp/sati_continue.dump 2>/dev/null; echo ok_var_tmp",
        "journalctl --disk-usage 2>/dev/null",
        "journalctl --vacuum-size=200M 2>/dev/null",
        "apt-get clean 2>/dev/null; apt-get autoclean -y 2>/dev/null; echo ok_apt",
        "find /var/log -type f -name '*.gz' -delete 2>/dev/null; echo ok_logs_gz",
        "find /var/log -type f -name '*.1' -delete 2>/dev/null; echo ok_logs_rot",
    ]
    for cmd in cmds:
        print(f"\n$ {cmd}")
        out = sudo(c, cmd) if cmd.startswith("journal") or "apt" in cmd else run(c, cmd)
        print(out[-2000:])

    print("\n=== reiniciando postgres ===")
    print(sudo(c, "systemctl restart postgresql@17-main 2>/dev/null || systemctl restart postgresql"))
    print(sudo(c, "systemctl status postgresql@17-main --no-pager | head -15"))

    print("\n=== depois ===")
    print(run(c, "df -h /var /var/tmp /tmp"))
    print(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='c2910'\" 2>&1",
        )
    )
    c.close()


if __name__ == "__main__":
    main()
