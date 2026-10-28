"""Deploy painel com licenças NFE + BI Web no Debian."""
import paramiko
import sys
from pathlib import Path

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
NFE = "/opt/nfe-web"
BI = "/home/oitamar/dashboard-financeiro-web"
LOCAL = Path(__file__).resolve().parents[1]
DEPLOY = LOCAL / "deploy" / "nfe-web"


def run(c, cmd, t=120):
    _, o, e = c.exec_command(cmd, timeout=t)
    o.channel.settimeout(t)
    return (o.read() + e.read()).decode("utf-8", errors="replace")


def sudo(c, cmd, t=120):
    i, o, _ = c.exec_command(f"sudo -S bash -c {repr(cmd)}", get_pty=True)
    i.write(PASS + "\n")
    i.flush()
    o.channel.settimeout(t)
    return o.read().decode("utf-8", errors="replace")


def upload(sftp, c, src: Path, dst: str, use_sudo: bool = True):
    tmp = f"/tmp/_deploy_{Path(dst).name}"
    print(f"Upload {dst}")
    sftp.put(str(src), tmp)
    if use_sudo:
        print(
            sudo(
                c,
                f"cp {tmp} {dst} && chown nfe-web:nfe-web {dst} 2>/dev/null || cp {tmp} {dst}",
            )
        )
    else:
        print(run(c, f"cp {tmp} {dst}"))


def sync_assets_painel(c):
    """Nginx serve /assets/painel/ — espelha frontend/painel/."""
    for nome in ("index.html", "painel.js", "painel.css"):
        src = f"{NFE}/frontend/painel/{nome}"
        dst = f"{NFE}/frontend/assets/painel/{nome}"
        print(sudo(c, f"cp {src} {dst} && chown nfe-web:nfe-web {dst}"))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    layout = run(c, f"test -f {BI}/app/__init__.py && echo app || echo flat").strip()
    print("Layout BIWEB:", layout)

    uploads = [
        (DEPLOY / "backend__app__routers__painel.py", f"{NFE}/backend/app/routers/painel.py"),
        (DEPLOY / "frontend__painel__painel.js", f"{NFE}/frontend/painel/painel.js"),
        (DEPLOY / "frontend__painel__index.html", f"{NFE}/frontend/painel/index.html"),
        (DEPLOY / "frontend__painel__painel.css", f"{NFE}/frontend/painel/painel.css"),
        (DEPLOY / "github_updater.py", f"{NFE}/github_updater.py"),
        (DEPLOY / "release_notas.py", f"{NFE}/release_notas.py"),
    ]
    if layout == "app":
        uploads += [
            (LOCAL / "app" / "utils" / "presenca_online.py", f"{BI}/app/utils/presenca_online.py", False),
            (LOCAL / "app" / "routes" / "api.py", f"{BI}/app/routes/api.py", False),
        ]

    sftp = c.open_sftp()
    for item in uploads:
        src, dst = item[0], item[1]
        use_sudo = item[2] if len(item) > 2 else True
        upload(sftp, c, src, dst, use_sudo=use_sudo)
    sftp.close()

    print("\n=== Espelhar assets nginx ===")
    sync_assets_painel(c)

    print("\n=== Reiniciar serviços ===")
    print(sudo(c, "systemctl restart nfe-web 2>&1 || true", t=30))
    print(run(c, "pkill -HUP -f 'gunicorn.*8000' 2>/dev/null || true", t=15))
    print(sudo(c, "systemctl reload nginx 2>&1 || true", t=15))

    print("\n=== Verificar rotas painel ===")
    print(run(c, f"grep -E '/licencas|/releases' {NFE}/backend/app/routers/painel.py || true"))
    print(run(c, f"test -f {NFE}/github_updater.py && echo github_updater_ok || echo github_updater_missing"))

    c.close()
    print("\nDeploy somente-web concluído.")


if __name__ == "__main__":
    main()
