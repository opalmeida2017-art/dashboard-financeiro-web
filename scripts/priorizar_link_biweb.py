#!/usr/bin/env python3
"""Prioriza um link BIWEB existente no Debian.

Este script e para casos em que o tenant ja existe (ex.: /biweb/batatao/)
e voce quer deixar somente esse link ativo, limpar navegadores orfaos e
dar prioridade best-effort aos processos do BIWEB.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.provisionar_link_biweb import (  # noqa: E402
    DEFAULT_APP_ROOT,
    DEFAULT_NFE_ROOT,
    DEFAULT_TENANTS_ROOT,
    ativar_modo_exclusivo,
    configurar_paths,
    limpar_chrome_orfaos,
    listar_processos,
    parar_processos_outros_tenants,
    priorizar_servicos,
    processos_navegador,
    slugify,
)


def slug_from_link(link: str) -> str:
    parsed = urlparse(link)
    path = parsed.path if parsed.scheme else link
    match = re.search(r"/(?:biweb|acesso)/([a-z0-9][a-z0-9_-]*)/?", path, re.I)
    if not match:
        return slugify(link)
    return slugify(match.group(1))


def tenant_registrado(slug: str) -> bool:
    try:
        from infra.tenant_licensing.bi_tenant_context import tenant_slug_registrado

        return bool(tenant_slug_registrado(slug))
    except Exception as exc:
        print(f"Aviso: nao foi possivel consultar registro central do tenant: {exc}")
        return True


def reiniciar_servicos(units: list[str], dry_run: bool) -> None:
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("Aviso: reinicio de servicos exige root; rode com sudo para aplicar.")
        return
    ativos: list[str] = []
    for unit in units:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            ativos.append(unit)
    if not ativos:
        print("Nenhum servico informado esta ativo para reiniciar.")
        return
    if dry_run:
        print("Servicos que seriam reiniciados: " + ", ".join(ativos))
        return
    subprocess.run(["systemctl", "restart", *ativos], check=False)
    print("Servicos reiniciados: " + ", ".join(ativos))


def mostrar_navegadores() -> None:
    navegadores = processos_navegador(listar_processos())
    if not navegadores:
        print("Nenhum navegador/chromedriver em execucao foi encontrado.")
        return
    print("Navegadores/processos relacionados ainda em execucao:")
    for proc in navegadores[:20]:
        print(
            f"  pid={proc['pid']} cpu={proc['cpu']} mem={proc['mem']} "
            f"tempo={proc['etime']} cmd={proc['comm']}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "link",
        help="Link externo ou slug, ex.: https://dadosfrete.duckdns.org:8443/biweb/batatao/",
    )
    parser.add_argument("--app-root", type=Path, default=DEFAULT_APP_ROOT)
    parser.add_argument("--nfe-root", type=Path, default=DEFAULT_NFE_ROOT)
    parser.add_argument("--tenants-root", type=Path, default=DEFAULT_TENANTS_ROOT)
    parser.add_argument(
        "--no-exclusive",
        action="store_true",
        help="Nao desativa os demais links no painel_bi_tenant.",
    )
    parser.add_argument(
        "--stop-other-tenant-processes",
        action="store_true",
        help="Encerra processos que indiquem explicitamente outro tenant nos argumentos.",
    )
    parser.add_argument(
        "--no-cleanup-browser-orphans",
        action="store_true",
        help="Nao roda limpeza segura de chromedriver/chrome orfaos.",
    )
    parser.add_argument(
        "--no-prioritize-services",
        action="store_true",
        help="Nao aplica renice/ionice best-effort nos processos BIWEB.",
    )
    parser.add_argument(
        "--restart-services",
        action="store_true",
        help="Reinicia gunicorn/worker/nginx ativos para limpar cache e aplicar bloqueios.",
    )
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        help="Nome de unit systemd adicional para reiniciar. Pode repetir.",
    )
    parser.add_argument(
        "--dry-run-processes",
        action="store_true",
        help="Lista acoes de processo/servico sem encerrar, priorizar ou reiniciar.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    slug = slug_from_link(args.link)
    configurar_paths(args.app_root, args.nfe_root, args.tenants_root)

    if not tenant_registrado(slug):
        raise SystemExit(f"Tenant {slug!r} nao esta registrado/ativo no BIWEB.")

    print(f"Priorizando tenant/link: {slug}")
    if not args.no_exclusive:
        ativar_modo_exclusivo(slug)
    if args.stop_other_tenant_processes:
        parar_processos_outros_tenants(slug, args.tenants_root, args.dry_run_processes)
    if not args.no_cleanup_browser_orphans:
        limpar_chrome_orfaos()
    mostrar_navegadores()
    if not args.no_prioritize_services:
        priorizar_servicos(args.app_root, args.dry_run_processes)
    if args.restart_services:
        units = [
            "gunicorn",
            "biweb-gunicorn",
            "biweb-worker",
            "nginx",
            *args.service,
        ]
        reiniciar_servicos(units, args.dry_run_processes)
    print("Priorizacao concluida.")


if __name__ == "__main__":
    main()
