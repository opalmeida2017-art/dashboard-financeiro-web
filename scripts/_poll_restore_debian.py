"""Acompanha restore_manual.log no Debian."""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
LOG = f"{APP}/restore_manual.log"


def run(c, cmd, timeout=30):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    return o.read().decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    for i in range(60):
        tail = run(c, f"tail -20 {LOG} 2>/dev/null || echo '(sem log ainda)'")
        print(f"--- poll {i + 1} ---")
        print(tail[-3000:])
        low = tail.lower()
        if "restore do schema sati concluído" in low:
            print("OK: restore concluído.")
            break
        if ("erro" in low or "traceback" in low) and i > 2:
            print("Restore parou com erro.")
            break
        time.sleep(20)

    print("=== tabelas w_carlos ===")
    print(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='w_carlos'\"",
        )
    )
    print(
        sudo(
            c,
            "-u postgres psql -d sat1_sati_is -tAc "
            "\"SELECT COUNT(*) FROM w_carlos.conhecimento\"",
        )
    )
    c.close()


if __name__ == "__main__":
    main()
