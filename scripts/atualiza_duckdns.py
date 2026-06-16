#!/usr/bin/env python3
"""
Atualiza dadosfrete.duckdns.org quando o IP público do roteador mudar.

Uso no Debian (cron a cada 5 min):
  */5 * * * * /usr/bin/python3 /home/oitamar/scripts/atualiza_duckdns.py >> /var/log/duckdns/atualiza.log 2>&1

Variáveis (arquivo opcional /home/oitamar/scripts/duckdns.env):
  DUCKDNS_TOKEN=seu_token
  DUCKDNS_DOMAIN=dadosfrete
  DUCKDNS_STATE_FILE=/var/log/duckdns/ultimo_ip.txt
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ENV_FILE = Path(os.getenv("DUCKDNS_ENV_FILE", "/home/oitamar/scripts/duckdns.env"))
STATE_FILE = Path(os.getenv("DUCKDNS_STATE_FILE", "/var/log/duckdns/ultimo_ip.txt"))
IP_APIS = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://checkip.amazonaws.com",
)


def _load_env_file() -> None:
    if not ENV_FILE.is_file():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def obter_ip_publico() -> str:
    last_err: Exception | None = None
    for url in IP_APIS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BIWEB-DuckDNS/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                ip = resp.read().decode("utf-8", errors="replace").strip()
            if ip and "." in ip:
                return ip
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"Não foi possível obter IP público: {last_err}")


def ler_ip_salvo() -> str:
    if not STATE_FILE.is_file():
        return ""
    return STATE_FILE.read_text(encoding="utf-8").strip()


def salvar_ip(ip: str) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(ip + "\n", encoding="utf-8")


def atualizar_duckdns(ip: str) -> str:
    token = os.getenv("DUCKDNS_TOKEN", "").strip()
    domain = os.getenv("DUCKDNS_DOMAIN", "dadosfrete").strip()
    if not token:
        raise RuntimeError("DUCKDNS_TOKEN não configurado")

    url = f"https://www.duckdns.org/update?domains={domain}&token={token}&ip={ip}"
    req = urllib.request.Request(url, headers={"User-Agent": "BIWEB-DuckDNS/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8", errors="replace").strip()
    if body not in ("OK", "KO"):
        raise RuntimeError(f"Resposta inesperada do DuckDNS: {body!r}")
    return body


def main() -> int:
    _load_env_file()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        ip_atual = obter_ip_publico()
        ip_anterior = ler_ip_salvo()
        mudou = ip_atual != ip_anterior

        if not mudou and ip_anterior:
            print(f"{agora} IP inalterado ({ip_atual}) — sem atualização")
            return 0

        resultado = atualizar_duckdns(ip_atual)
        salvar_ip(ip_atual)
        status = "alterado" if mudou else "primeira execução"
        print(
            f"{agora} DuckDNS {resultado} | IP {status}: "
            f"{ip_anterior or '—'} -> {ip_atual}"
        )
        return 0 if resultado == "OK" else 1

    except Exception as exc:
        print(f"{agora} ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
