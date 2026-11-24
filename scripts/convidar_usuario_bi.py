"""Cria/atualiza um usuário do BI e imprime o link para ele definir a senha.

Uso (no Debian, na pasta do projeto):
    python scripts/convidar_usuario_bi.py --tenant transporte-brasil \\
        --email diretor@empresa.com.br --nome "Fulano" --perfil diretor

Perfis: admin, diretor, comercial, financeiro, operacao.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.env_loader import load_env  # noqa: E402

load_env()

from app.security import PERFIS, criar_ou_atualizar_usuario  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenant", required=True, help="slug da transportadora (ex.: transporte-brasil)")
    ap.add_argument("--email", required=True)
    ap.add_argument("--nome", default="")
    ap.add_argument("--perfil", required=True, choices=sorted(PERFIS))
    args = ap.parse_args()
    try:
        item = criar_ou_atualizar_usuario(args.tenant.strip().lower(), args.email, args.nome, args.perfil)
    except ValueError as exc:
        print(f"ERRO: {exc}")
        return 1
    print(f"Usuário {item['email']} ({PERFIS[item['perfil']]}) pronto.")
    print(f"Link para definir a senha (vale {item['convite_expira_horas']} h, uso único):")
    print(item["convite_url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
