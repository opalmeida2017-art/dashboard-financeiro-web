"""Diagnóstico rápido do restore no Debian."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
APP = "/home/oitamar/dashboard-financeiro-web"
LOG = f"{APP}/restore_manual.log"


def run(c, cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    o.channel.settimeout(timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, timeout=60):
    i, o, _ = c.exec_command(f"sudo -S {cmd}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(timeout)
    return o.read().decode("utf-8", errors="replace")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print("=== processos restore ===")
    print(run(c, "ps aux | grep -E 'pg_restore|sati_db|processar_arquivo' | grep -v grep"))

    print("=== log head (80) ===")
    print(run(c, f"head -80 {LOG}"))

    print("=== log tail (100) ===")
    print(run(c, f"tail -100 {LOG}"))

    print("=== grep ERRO/concluído/pre-data ===")
    print(run(c, f"grep -nE 'ERRO|concluí|pre-data|tabelas|schema|Traceback|FALHA|sucesso' {LOG} | tail -40"))

    print("=== schemas ===")
    print(sudo(c, "-u postgres psql -d sat1_sati_is -c \"SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE '%carlos%' OR schema_name LIKE 'c2910%';\""))

    print("=== tabelas por schema ===")
    print(sudo(c, "-u postgres psql -d sat1_sati_is -c \"SELECT table_schema, COUNT(*) FROM information_schema.tables WHERE table_schema IN ('w_carlos','c2910','public') GROUP BY 1;\""))

    print("=== disco ===")
    print(run(c, "df -h /tmp /home /var/tmp"))

    c.close()


if __name__ == "__main__":
    main()
