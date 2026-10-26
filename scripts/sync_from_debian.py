#!/usr/bin/env python3
"""
Baixa do Debian → Windows: configs de tenant, dumps SATI e (opcional) código.

Uso típico (primeira vez):
    python scripts/sync_from_debian.py --tenant transporte-brasil
    python scripts/setup_dev_windows.py --tenant transporte-brasil

Opções:
    --tenant transporte-brasil|jeremias|rio-bonito|wcarlos|all
    --code          sobrescreve app/, sati_integration/, frontend/ etc. do servidor
    --no-zip        não baixa SATI-cXXXX-atual.zip (só configs)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"
BI_REMOTE = "/home/oitamar/dashboard-financeiro-web"
TENANTS_REMOTE = "/opt/biweb/tenants"
MIRROR = ROOT / "dev" / "debian_mirror"

TENANTS = {
    "transporte-brasil": {
        "label": "Transporte Brasil",
        "debian_dir": "Transporte-Brasil",
        "schema": "c3332",
        "apartamento_id": 3,
        "zip_remote": f"{TENANTS_REMOTE}/Transporte-Brasil/downloads/3/SATI-c3332-atual.zip",
        "zip_remote_alt": f"{TENANTS_REMOTE}/Transporte-Brasil/downloads/1/SATI-c3332-atual.zip",
    },
    "jeremias": {
        "label": "Jeremias",
        "debian_dir": "Jeremias",
        "schema": "c3332",
        "apartamento_id": 6,
        "zip_remote": f"{TENANTS_REMOTE}/Jeremias/downloads/6/SATI-c3332-atual.zip",
    },
    "rio-bonito": {
        "label": "Rio Bonito",
        "debian_dir": "rio-bonito",
        "schema": "c3219",
        "apartamento_id": 2,
        "zip_remote": f"{TENANTS_REMOTE}/rio-bonito/downloads/2/SATI-c3219-atual.zip",
    },
    "wcarlos": {
        "label": "W Carlos",
        "debian_dir": "wcarlos",
        "schema": "c2910",
        "apartamento_id": 1,
        "zip_remote": f"{TENANTS_REMOTE}/wcarlos/downloads/1/SATI-c2910-atual.zip",
    },
}

CODE_DIRS = ["app", "sati_integration", "infra", "frontend", "migrations"]
CODE_FILES = ["wsgi.py", "worker.py", "requirements.txt", "run_dev.py"]


def _connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    return c


def _remote_exists(sftp: paramiko.SFTPClient, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except OSError:
        return False


def _pull_file(sftp: paramiko.SFTPClient, remote: str, local: Path) -> bool:
    if not _remote_exists(sftp, remote):
        return False
    local.parent.mkdir(parents=True, exist_ok=True)
    sftp.get(remote, str(local))
    return True


def _pull_tree(sftp: paramiko.SFTPClient, remote_dir: str, local_dir: Path) -> int:
    """Baixa diretório recursivamente (SFTP)."""
    n = 0
    try:
        for entry in sftp.listdir_attr(remote_dir):
            rname = entry.filename
            if rname.startswith("."):
                continue
            rpath = f"{remote_dir.rstrip('/')}/{rname}"
            lpath = local_dir / rname
            if entry.st_mode & 0o40000:
                n += _pull_tree(sftp, rpath, lpath)
            else:
                lpath.parent.mkdir(parents=True, exist_ok=True)
                sftp.get(rpath, str(lpath))
                n += 1
    except OSError as exc:
        print(f"  aviso: {remote_dir}: {exc}")
    return n


def sync_tenant(sftp: paramiko.SFTPClient, slug: str, *, pull_zip: bool) -> dict:
    cfg = TENANTS[slug]
    apt = cfg["apartamento_id"]
    schema = cfg["schema"]
    debian_dir = cfg["debian_dir"]
    out: dict = {"slug": slug, "schema": schema, "apartamento_id": apt, "files": []}

    mirror_tenant = MIRROR / "tenants" / slug
    mirror_tenant.mkdir(parents=True, exist_ok=True)

    for env_name in ("tenant.env", ".env"):
        remote = f"{TENANTS_REMOTE}/{debian_dir}/{env_name}"
        local = mirror_tenant / env_name
        if _pull_file(sftp, remote, local):
            print(f"  ok {env_name} → {local.relative_to(ROOT)}")
            out["files"].append(str(local.relative_to(ROOT)))

    if pull_zip:
        dest = ROOT / "downloads" / str(apt) / f"SATI-{schema}-atual.zip"
        pulled = False
        for remote in (cfg.get("zip_remote"), cfg.get("zip_remote_alt")):
            if not remote:
                continue
            if _pull_file(sftp, remote, dest):
                mb = dest.stat().st_size / (1024 * 1024)
                print(f"  ok SATI zip ({mb:.1f} MB) → {dest.relative_to(ROOT)}")
                out["files"].append(str(dest.relative_to(ROOT)))
                out["zip"] = str(dest)
                pulled = True
                break
        if not pulled:
            print(f"  aviso: ZIP SATI não encontrado para {slug}")

    return out


def sync_code(sftp: paramiko.SFTPClient) -> None:
    print("Baixando código do Debian (sobrescreve local)...")
    for d in CODE_DIRS:
        remote = f"{BI_REMOTE}/{d}"
        local = ROOT / d
        n = _pull_tree(sftp, remote, local)
        print(f"  {d}/ — {n} arquivos")
    for f in CODE_FILES:
        remote = f"{BI_REMOTE}/{f}"
        local = ROOT / f
        if _pull_file(sftp, remote, local):
            print(f"  ok {f}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Sync Debian → Windows (dev)")
    ap.add_argument(
        "--tenant",
        default="transporte-brasil",
        choices=[*TENANTS.keys(), "all"],
        help="Tenant para baixar config + dump SATI",
    )
    ap.add_argument("--code", action="store_true", help="Baixar também código do servidor")
    ap.add_argument("--no-zip", action="store_true", help="Não baixar ZIP SATI")
    args = ap.parse_args()

    MIRROR.mkdir(parents=True, exist_ok=True)
    slugs = list(TENANTS.keys()) if args.tenant == "all" else [args.tenant]

    print(f"Conectando {HOST}…")
    client = _connect()
    sftp = client.open_sftp()
    manifest_entries = []

    try:
        if args.code:
            sync_code(sftp)

        for slug in slugs:
            print(f"\nTenant: {slug} ({TENANTS[slug]['label']})")
            manifest_entries.append(
                sync_tenant(sftp, slug, pull_zip=not args.no_zip)
            )
    finally:
        sftp.close()
        client.close()

    manifest = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "host": HOST,
        "tenants": manifest_entries,
    }
    manifest_path = MIRROR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nManifest: {manifest_path.relative_to(ROOT)}")
    print("\nPróximo passo:")
    print("  python scripts/setup_dev_windows.py --tenant", slugs[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
