#!/usr/bin/env python3
"""Provisiona um link/tenant BIWEB para uma URL SATI no Debian.

Uso tipico no servidor:

    cd /home/oitamar/dashboard-financeiro-web
    ./venv/bin/python scripts/provisionar_link_biweb.py \
        --slug leiliane \
        --razao Leiliane \
        --sati-url https://sat3.intersite.com.br/c3388 \
        --sati-user leiliane \
        --exclusive \
        --cleanup-browser-orphans \
        --prioritize-services

A senha pode ser informada por --sati-password, pela variavel SATI_PASSWORD
ou digitada no prompt. O valor nao e gravado em arquivo versionado.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Iterable


DEFAULT_APP_ROOT = Path("/home/oitamar/dashboard-financeiro-web")
DEFAULT_NFE_ROOT = Path("/opt/nfe-web")
DEFAULT_TENANTS_ROOT = Path("/opt/biweb/tenants")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-_")
    if not slug:
        raise SystemExit("Informe um slug valido.")
    return slug[:40]


def sati_codigo(url: str) -> str:
    match = re.search(r"/(c\d+)(?:/?|\?.*)$", (url or "").strip(), re.I)
    if not match:
        match = re.search(r"(c\d+)", (url or "").strip(), re.I)
    if not match:
        raise SystemExit("Nao foi possivel identificar o codigo SATI (ex.: c3388) na URL.")
    return match.group(1).lower()


def mascarar(valor: str, inicio: int = 3) -> str:
    if not valor:
        return ""
    return valor[:inicio] + "***"


def carregar_env(path: Path, override: bool = False) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or (key in os.environ and not override):
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def configurar_paths(app_root: Path, nfe_root: Path, tenants_root: Path) -> None:
    os.environ.setdefault("BI_TENANTS_ROOT", str(tenants_root))
    os.chdir(app_root)
    for path in (str(app_root), str(nfe_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    carregar_env(app_root / ".env", override=False)


def importar_provisioner(nfe_root: Path):
    if str(nfe_root) not in sys.path:
        sys.path.insert(0, str(nfe_root))
    try:
        from deploy import provision_bi_tenant
    except Exception as exc:  # pragma: no cover - depende do Debian de producao.
        raise SystemExit(
            "Nao foi possivel importar deploy.provision_bi_tenant. "
            "Rode este script no Debian onde /opt/nfe-web esta instalado."
        ) from exc
    return provision_bi_tenant


def atualizar_tenant_env(
    tenants_root: Path,
    slug: str,
    razao: str,
    pg_database: str,
    sati_url: str,
) -> Path:
    tenant_dir = tenants_root / slug
    tenant_dir.mkdir(parents=True, exist_ok=True)
    (tenant_dir / "downloads").mkdir(exist_ok=True)
    (tenant_dir / "logs").mkdir(exist_ok=True)
    env_path = tenant_dir / "tenant.env"
    existente: dict[str, str] = {}
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if raw.strip() and not raw.strip().startswith("#") and "=" in raw:
                key, value = raw.split("=", 1)
                existente[key.strip()] = value.strip()

    codigo = sati_codigo(sati_url)
    valores = {
        "BI_TENANT_SLUG": slug,
        "BI_TENANT_DIR": str(tenant_dir),
        "BI_PG_DATABASE": pg_database,
        "RAZAO_SOCIAL": razao,
        "USE_SATI_SOURCE": "true",
        "SATI_SCHEMA": codigo,
        "SATI_URL": sati_url,
    }
    existente.update(valores)
    env_path.write_text(
        "\n".join(f"{key}={value}" for key, value in existente.items()) + "\n",
        encoding="utf-8",
    )
    try:
        env_path.chmod(0o600)
    except OSError:
        pass
    return tenant_dir


def provisionar_tenant(args: argparse.Namespace) -> dict:
    provisioner = importar_provisioner(args.nfe_root)
    resultado = provisioner.criar_instancia_bi(
        args.razao,
        args.slug,
        args.sati_url,
    )
    if not isinstance(resultado, dict):
        resultado = {}
    pg_database = resultado.get("pg_database") or f"bi_{args.slug.replace('-', '_')}"
    tenant_dir = atualizar_tenant_env(
        args.tenants_root,
        args.slug,
        args.razao,
        pg_database,
        args.sati_url,
    )
    resultado.setdefault("slug", args.slug)
    resultado.setdefault("pg_database", pg_database)
    resultado.setdefault("tenant_dir", str(tenant_dir))
    return resultado


def configurar_credenciais_robo(args: argparse.Namespace, tenant: dict) -> int:
    from infra.tenant_licensing.bi_tenant_runtime import prepare_robot_context

    ok = prepare_robot_context(tenant_slug=args.slug)
    if not ok:
        raise SystemExit(f"Tenant {args.slug!r} nao carregou DATABASE_URL via tenant.env.")

    from app.data import data_manager as dm
    from app.data.tenant import default_transportadora_id

    apartamento_id = tenant.get("apartamento_id")
    if apartamento_id in (None, ""):
        apartamento_id = default_transportadora_id()
    apartamento_id = int(apartamento_id)
    codigo = sati_codigo(args.sati_url)

    dm.salvar_configuracoes_robo(
        apartamento_id,
        {
            "URL_LOGIN": args.sati_url,
            "USUARIO_ROBO": args.sati_user,
            "SENHA_ROBO": args.sati_password,
            "USE_SATI_SOURCE": "true",
            "SATI_PG_SCHEMA": codigo,
            "SATI_URL_CODIGO": codigo,
        },
    )
    cfg = dm.ler_configuracoes_robo(apartamento_id)
    faltando = [
        key for key in ("URL_LOGIN", "USUARIO_ROBO", "SENHA_ROBO") if not cfg.get(key)
    ]
    if faltando:
        raise SystemExit(f"Credenciais incompletas no tenant: {', '.join(faltando)}")
    return apartamento_id


def ativar_modo_exclusivo(slug: str) -> None:
    from infra.tenant_licensing.bi_tenant_context import _central_conn

    conn = _central_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE painel_bi_tenant
            SET ativo = CASE WHEN LOWER(slug) = %s THEN TRUE ELSE FALSE END,
                updated_at = NOW()
            """,
            (slug.lower(),),
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Modo exclusivo ativo: somente o link {slug!r} ficou liberado.")


def listar_processos() -> list[dict[str, str]]:
    out = subprocess.check_output(
        ["ps", "-eo", "pid,ppid,user,comm,%cpu,%mem,etime,args", "--sort=-%cpu"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    linhas = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        pid, ppid, user, comm, cpu, mem, etime, args = parts
        linhas.append(
            {
                "pid": pid,
                "ppid": ppid,
                "user": user,
                "comm": comm,
                "cpu": cpu,
                "mem": mem,
                "etime": etime,
                "args": args,
            }
        )
    return linhas


def processos_navegador(processos: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    termos = (
        "chrome",
        "chromium",
        "chromedriver",
        "firefox",
        "geckodriver",
        "playwright",
        "selenium",
    )
    return [
        proc
        for proc in processos
        if any(term in (proc["comm"] + " " + proc["args"]).lower() for term in termos)
    ]


def limpar_chrome_orfaos() -> None:
    try:
        from sati_integration.robos.chrome_cleanup import (
            limpar_chrome_orfaos as cleanup,
            limpar_perfis_antigos,
        )
    except Exception as exc:
        print(f"Aviso: limpeza de Chrome nao disponivel: {exc}")
        return
    resultado = cleanup()
    perfis = limpar_perfis_antigos()
    print(f"Chrome orfao removido: {resultado}; perfis antigos removidos: {perfis}")


def parar_processos_outros_tenants(slug: str, tenants_root: Path, dry_run: bool) -> None:
    if not tenants_root.is_dir():
        return
    outros = [p.name for p in tenants_root.iterdir() if p.is_dir() and p.name != slug]
    encerrados: list[str] = []
    for proc in listar_processos():
        args = proc["args"]
        if f"{tenants_root}/{slug}" in args or f"BI_TENANT_SLUG={slug}" in args:
            continue
        if not any(
            f"{tenants_root}/{outro}" in args or f"BI_TENANT_SLUG={outro}" in args
            for outro in outros
        ):
            continue
        pid = int(proc["pid"])
        encerrados.append(f"{pid}:{proc['comm']}")
        if not dry_run:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    if encerrados:
        acao = "Detectados" if dry_run else "Encerrados"
        print(f"{acao} processos de outros tenants: {', '.join(encerrados)}")


def priorizar_servicos(app_root: Path, dry_run: bool) -> None:
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("Aviso: ajuste de prioridade exige root; rode com sudo para aplicar renice.")
        return

    alvos = []
    root_txt = str(app_root)
    for proc in listar_processos():
        args = proc["args"]
        texto = (proc["comm"] + " " + args).lower()
        if root_txt in args and ("gunicorn" in texto or "rq" in texto or "worker" in texto):
            alvos.append(proc["pid"])

    if not alvos:
        print("Nenhum processo gunicorn/worker do BIWEB encontrado para priorizar.")
        return
    if dry_run:
        print("Processos que seriam priorizados: " + ", ".join(alvos))
        return
    subprocess.run(["renice", "-n", "-5", "-p", *alvos], check=False)
    subprocess.run(["ionice", "-c2", "-n0", "-p", *alvos], check=False)


def enfileirar_atualizacao(apartamento_id: int, slug: str) -> None:
    from redis import Redis
    from rq import Queue

    from app.core import logic

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    fila = Queue("default", connection=Redis.from_url(redis_url))
    job = fila.enqueue(
        logic.executar_atualizacao_bd_sati,
        apartamento_id,
        tenant_slug=slug,
        job_timeout=7200,
    )
    print(f"Atualizacao SATI enfileirada para {slug}: job_id={job.id}")


def resolver_senha(args: argparse.Namespace) -> None:
    if args.sati_password:
        return
    args.sati_password = os.getenv("SATI_PASSWORD") or os.getenv("SENHA_ROBO") or ""
    if args.sati_password:
        return
    args.sati_password = getpass.getpass("Senha SATI: ")
    if not args.sati_password:
        raise SystemExit("Senha SATI nao informada.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True, help="Slug do link, ex.: leiliane")
    parser.add_argument("--razao", default="", help="Nome exibido da transportadora")
    parser.add_argument("--sati-url", required=True, help="URL SATI, ex.: https://.../c3388")
    parser.add_argument("--sati-user", default=os.getenv("SATI_USER") or os.getenv("USUARIO_ROBO") or "")
    parser.add_argument("--sati-password", default=os.getenv("SATI_PASSWORD") or os.getenv("SENHA_ROBO") or "")
    parser.add_argument("--app-root", type=Path, default=DEFAULT_APP_ROOT)
    parser.add_argument("--nfe-root", type=Path, default=DEFAULT_NFE_ROOT)
    parser.add_argument("--tenants-root", type=Path, default=DEFAULT_TENANTS_ROOT)
    parser.add_argument(
        "--exclusive",
        action="store_true",
        help="Desativa os demais links no painel_bi_tenant.",
    )
    parser.add_argument(
        "--stop-other-tenant-processes",
        action="store_true",
        help="Encerra somente processos que indiquem explicitamente outro tenant nos argumentos.",
    )
    parser.add_argument(
        "--cleanup-browser-orphans",
        action="store_true",
        help="Roda a limpeza segura de chromedriver/chrome orfaos.",
    )
    parser.add_argument(
        "--prioritize-services",
        action="store_true",
        help="Aplica renice/ionice best-effort em gunicorn/worker do BIWEB.",
    )
    parser.add_argument(
        "--enqueue-update",
        action="store_true",
        help="Enfileira a atualizacao/restore SATI do tenant ao final.",
    )
    parser.add_argument(
        "--dry-run-processes",
        action="store_true",
        help="Apenas lista acoes de processos, sem encerrar/priorizar.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.slug = slugify(args.slug)
    args.razao = (args.razao or args.slug).strip()
    args.sati_url = args.sati_url.strip()
    args.sati_user = args.sati_user.strip()
    if not args.sati_user:
        raise SystemExit("Usuario SATI nao informado.")
    resolver_senha(args)

    configurar_paths(args.app_root, args.nfe_root, args.tenants_root)
    tenant = provisionar_tenant(args)
    apartamento_id = configurar_credenciais_robo(args, tenant)

    if args.exclusive:
        ativar_modo_exclusivo(args.slug)
    if args.stop_other_tenant_processes:
        parar_processos_outros_tenants(args.slug, args.tenants_root, args.dry_run_processes)
    if args.cleanup_browser_orphans:
        limpar_chrome_orfaos()

    navegadores = processos_navegador(listar_processos())
    if navegadores:
        print("Navegadores/processos relacionados ainda em execucao:")
        for proc in navegadores[:20]:
            print(
                f"  pid={proc['pid']} cpu={proc['cpu']} mem={proc['mem']} "
                f"tempo={proc['etime']} cmd={proc['comm']}"
            )
    else:
        print("Nenhum navegador/chromedriver em execucao foi encontrado.")

    if args.prioritize_services:
        priorizar_servicos(args.app_root, args.dry_run_processes)
    if args.enqueue_update:
        enfileirar_atualizacao(apartamento_id, args.slug)

    url = tenant.get("url") or f"/biweb/{args.slug}/"
    print("Provisionamento concluido.")
    print(f"  link: {url}")
    print(f"  slug: {args.slug}")
    print(f"  banco: {tenant.get('pg_database')}")
    print(f"  apartamento_id: {apartamento_id}")
    print(f"  SATI: {args.sati_url}")
    print(f"  usuario: {mascarar(args.sati_user)}")


if __name__ == "__main__":
    main()
